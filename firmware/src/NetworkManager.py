from src.NetworkConfig import NetworkConfig
from src.UploadConfig import UploadConfig
from src.TimeManager import TimeManager
from src.CameraConfig import CameraConfig
from src.Tools import Tools
import network
import time
import ntptime
import os
import asyncio
import json
import gc

class NetworkManager:
    # Initializes the network manager.
    def __init__(self, file_manager, log_manager):
        self._tools = Tools()
        self._file_manager = file_manager
        self._log_manager = log_manager
        self._upload_config = UploadConfig()
        self._time_manager = TimeManager()
        self._camera_config = CameraConfig()

        self._network_config = NetworkConfig()
        self._ssid = self._network_config.ssid()
        self._key = self._network_config.key()

        self._wlan = network.WLAN(network.STA_IF)
        self._wlan.active(True)

        # References the currently running per-file upload task.
        self._upload_task = None

    def initialize(self):
        self._connect()
        if self._wlan.isconnected():
            self._sync_time()

    # Connects the device to the configured WiFi network.
    def _connect(self):
        self._wlan.connect(self._ssid, self._key)

        attempts = 0

        while (
            not self._wlan.isconnected()
            and attempts < self._upload_config.connect_max_attempts()
        ):
            print('Trying to connect to "{:s}"...'.format(self._ssid))
            attempts += 1
            time.sleep_ms(self._upload_config.connect_poll_ms())

        # A valid IP address should now be assigned by DHCP.
        #print("WiFi connected:", self._wlan.ifconfig())
        if self._wlan.isconnected():
            print("Wi-Fi connected")
        else:
            print("Wi-Fi not connected")

    async def _reconnect(self):
        for delay in self._upload_config.backoff_s():
            self._wlan.disconnect()
            self._wlan.connect(self._ssid, self._key)
            deadline = time.ticks_add(time.ticks_ms(), self._upload_config.reconnect_timeout_ms())
            while not self._wlan.isconnected():
                if time.ticks_diff(deadline, time.ticks_ms()) <= 0:
                    break
                await asyncio.sleep_ms(self._upload_config.reconnect_poll_ms())
            if self._wlan.isconnected():
                print("WiFi reconnected")
                self._log_manager.info("Wi-Fi reconnected")
                # Resynchronize the RTC after network recovery.
                self._sync_time()
                return True
            print("Reconnect failed, retrying in", delay, "seconds")
            self._log_manager.warning("Reconnect failed")
            await asyncio.sleep(delay)
        return False

    async def _radio_power_cycle(self):
        print("Power cycling Wi-Fi interface")
        self._log_manager.info("Power cycling Wi-Fi interface")
        self._wlan.active(False)
        await asyncio.sleep(self._upload_config.radio_restart_delay_s())
        self._wlan.active(True)
        return await self._reconnect()

    def _sync_time(self):
        # NTP initially sets the RTC to UTC.
        ntptime.settime()
        # Convert the RTC to Finnish local time so filesystem timestamps
        # use the correct winter/summer time.
        self._time_manager.set_finland_local_time()
        print("Date and time updated:", time.localtime())

    async def upload_task(self):
        # Allow both camera interfaces and the first prebuffer cycle to stabilize.
        await asyncio.sleep_ms(self._upload_config.startup_delay_ms())
        while True:
            try:
                if self._wlan.isconnected():
                    await self._upload_mjpeg_files()
                else:
                    reconnected = await self._reconnect()
                    if not reconnected:
                        await self._radio_power_cycle()
            except Exception as error:
                # Network/AWS failures must never terminate the embedded system.
                print("Upload task error:", error)
                self._log_manager.error("Upload task error: {}".format(error))
            await asyncio.sleep_ms(self._upload_config.upload_time_ms())

    async def _upload_mjpeg_files(self):
        files = self._file_manager.get_files()
        if files:
            for file in files:
                if self._wlan.isconnected():
                    self._log_manager.info("Upload cycle started")
                    self._tools.print_memory_status("Memory before upload")
                    upload_succeeded = False
                    try:
                        new_file = self._file_manager.check_if_lepton(file)
                        if new_file:
                            file = new_file
                        try:
                            #upload_succeeded = await self._upload_mjpeg(file)
                            self._upload_task = asyncio.create_task(self._upload_mjpeg(file))
                            upload_succeeded = await self._upload_task
                            #if upload_succeeded:
                                #self._file_manager.delete_file(file)
                                #self._log_manager.info(f"File deleted {file}")
                                #self._file_manager.mark_file_as_sent(file)
                        except asyncio.CancelledError:
                            self._log_manager.warning("Upload interrupted for recording: {}".format(file))
                        finally:
                            self._upload_task = None
                        if upload_succeeded:
                            # self._file_manager.delete_file(file)
                            # self._log_manager.info(f"File deleted {file}")
                            self._file_manager.mark_file_as_sent(file)
                        else:
                            self._log_manager.warning("Upload cycle stopped after failed upload")
                            break
                    except Exception as error:
                        self._log_manager.error("Upload file error: {}".format(error))
                    finally:
                        self._log_manager.info("Post-upload cleanup started")
                        self._tools.cleanup_memory()
                        self._tools.print_memory_status("Memory after upload cleanup")
                        # Give the network stack time to release TLS resources.
                        await asyncio.sleep_ms(self._upload_config.post_upload_delay_ms())
                else:
                    break

    # Uploads an MJPEG file to AWS S3 using a presigned URL.
    async def _upload_mjpeg(self, filename):
        self._log_manager.info("Upload started: {}".format(filename))
        self._tools.cleanup_memory()
        self._tools.print_memory_status("Memory after cleanup -> next uploading")

        metadata = self._file_manager.get_video_metadata(filename)
        data = {
            "camera_id": self._camera_config.camera_id(),
            "event_id": metadata["event_id"],
            "sensor": metadata["sensor"]
        }

        self._log_manager.info("Requesting presigned URL")
        # Request a presigned S3 upload URL and separate it into
        # the hostname and request path required for the HTTP request.
        upload_url = await self._get_upload_url(data)
        self._log_manager.info("Presigned URL received")

        host, path = self._parse_https_url(upload_url)
        # Read the file size for the HTTP Content-Length header.
        file_size = os.stat(filename)[6]

        print("Uploading:", filename)
        print("File size:", file_size)

        reader = None
        writer = None

        try:
            self._log_manager.info("Opening S3 TLS connection")

            reader, writer = await asyncio.open_connection(
                host, self._upload_config.https_port(), ssl=True
            )

            self._log_manager.info("S3 TLS connected")

            await self._send_upload_header(writer, host, path, file_size)

            upload_start_time = time.ticks_ms()
            last_upload_progress = time.ticks_ms()

            # Allocate the upload block once and reuse it for the complete file.
            # This avoids allocating a new bytes object for every file read.
            chunk = bytearray(self._upload_config.upload_chunk_size())
            mv = memoryview(chunk)

            self._log_manager.info("File streaming started")

            uploaded_bytes = 0
            last_memory_log = time.ticks_ms()

            self._log_manager.info("Upload memory at start: {}".format(gc.mem_free()))

            # Stream the file directly from storage to S3 in blocks
            # instead of loading the complete MJPEG file into RAM.
            with open(filename, "rb") as file:
                try:
                    while True:
                        if self._wlan.isconnected():
                            now = time.ticks_ms()
                            if time.ticks_diff(now, last_upload_progress) > self._upload_config.upload_progress_timeout_ms():
                                self._log_manager.warning("Upload interrupted too long, retrying later")
                                return False

                            # Read the next block directly into the existing chunk buffer.
                            try:
                                bytes_read = file.readinto(chunk)
                            except Exception as err:
                                self._log_manager.error("SD card read failed: {}".format(err))
                                return False

                            # An empty read indicates that the end of the file
                            # has been reached.
                            if not bytes_read:
                                break

                            # Ensure the complete block is written before reading
                            try:
                                writer.write(mv[:bytes_read])
                            except Exception as err:
                                self._log_manager.error("Upload socket write failed: {}".format(err))
                                return False

                            try:
                                await asyncio.wait_for(writer.drain(), self._upload_config.network_operation_timeout_s())
                            except asyncio.TimeoutError:
                                self._log_manager.warning("Upload stream timeout")
                                print("Upload stream timeout")
                                return False

                            last_upload_progress = time.ticks_ms()
                            uploaded_bytes += bytes_read

                            if time.ticks_diff(last_upload_progress, last_memory_log
                            ) >= self._upload_config.memory_log_interval_ms():
                                upload_percent = uploaded_bytes * 100 // file_size

                                self._log_manager.info(
                                    "Upload progress: {}%, free memory: {}".format(
                                        upload_percent,
                                        gc.mem_free()
                                    )
                                )
                                last_memory_log = last_upload_progress
                        else:
                            self._log_manager.warning("Wi-Fi disconnected during upload, retrying later")
                            return False

                except Exception as err:
                    print("File streaming error", err)
                    self._log_manager.error("File streaming error: {}".format(err))
                    return False

            self._log_manager.info("Upload memory after streaming: {}".format(gc.mem_free()))

            try:
                await asyncio.wait_for(self._check_upload_response(reader), self._upload_config.network_operation_timeout_s())
            except asyncio.TimeoutError:
                self._log_manager.warning("Upload response failed")
                return False

            self._log_manager.info(f"{filename} uploaded successfully")
            # Calculate the total upload duration and average transfer speed.
            upload_duration_ms = time.ticks_diff(time.ticks_ms(), upload_start_time)
            print("Upload duration ms:", upload_duration_ms)
            print("Upload speed KiB/s:", (file_size * 1000) // upload_duration_ms // 1024)
            return True

        except asyncio.CancelledError:
            self._log_manager.warning("MJPEG upload cancelled before recording")
            raise
        except Exception as error:
            print("MJPEG upload error:", error)
            self._log_manager.info("MJPEG upload error")
            return False

        finally:
            if writer is not None:
                try:
                    writer.close()
                    await writer.wait_closed()
                    self._log_manager.info("S3 TLS connection closed")
                except Exception as error:
                    self._log_manager.info("Writer close error")
                    print("Writer close error:", error)

    async def _send_upload_header(self, writer, host, path, file_size):
        # Build the HTTP PUT request header.
        # The presigned URL already contains the authentication
        # parameters required by S3.
        request_header = (
            "PUT {} HTTP/1.1\r\n"
            "Host: {}\r\n"
            "Content-Length: {}\r\n"
            "Connection: close\r\n"
            "\r\n"
        ).format(path, host, file_size)

        # Send the complete request header before transmitting
        # the MJPEG file contents.
        writer.write(request_header.encode())
        await writer.drain()

    async def _check_upload_response(self, reader):
        # Read the first line of the HTTP response, for example:
        # HTTP/1.1 200 OK
        status_line = await reader.readline()
        self._log_manager.info("S3 response received")

        if status_line:
            print("S3 response:", status_line)
            # A successful S3 PUT upload returns HTTP status 200.
            # Read and print the remaining response only when the upload fails.
            if b" 200 " not in status_line:
                response_body = await reader.read()
                print("S3 error response:", response_body)
                self._log_manager.info("MJPEG upload failed")
                raise OSError("MJPEG upload failed")
        else:
            # A missing response usually means that the connection was
            # closed before S3 returned an HTTP status.
            self._log_manager.info("No response received from S3")
            raise OSError("No response received from S3")

    # Sends a JSON POST request over HTTPS and returns the JSON response.
    async def _post_json(self, url, data):
        host, path = self._parse_https_url(url)
        # Convert the Python object into a JSON request body.
        body = json.dumps(data)
        reader = None
        writer = None

        try:
            self._log_manager.info("Opening presigned URL TLS connection")
            reader, writer = await asyncio.open_connection(
                host, self._upload_config.https_port(), ssl=True
            )
            self._log_manager.info("Presigned URL TLS connected")

            # Build the HTTP POST request header.
            request = (
                "POST {} HTTP/1.1\r\n"
                "Host: {}\r\n"
                "Content-Type: application/json\r\n"
                "Content-Length: {}\r\n"
                "Connection: close\r\n"
                "\r\n"
                "{}"
            ).format(path, host, len(body), body)

            # Send the request headers and JSON body.
            writer.write(request.encode())
            await writer.drain()

            # Read the HTTP status line.
            status_line = await reader.readline()
            if status_line:
                if b" 200 " in status_line:
                    # Skip HTTP response headers.
                    while True:
                        line = await reader.readline()
                        if line == b"\r\n":
                            break
                    # Read and decode the JSON response body.
                    response_body = await reader.read()
                    return json.loads(response_body)
                else:
                    self._log_manager.info("HTTP POST failed")
                    raise OSError("HTTP POST failed: {}".format(status_line))
            else:
                self._log_manager.info("No response received")
                raise OSError("No response received")

        except Exception as error:
            self._log_manager.info("POST error")
            print("POST error:", error)
            raise

        finally:
            if writer is not None:
                try:
                    writer.close()
                    await writer.wait_closed()
                    self._log_manager.info("Presigned URL TLS connection closed")
                except Exception as error:
                    print("Writer close error:", error)
                    raise

    # Requests a temporary S3 upload URL from AWS.
    async def _get_upload_url(self, data):
        try:
            response = await asyncio.wait_for(
                self._post_json(self._network_config.url_endpoint(), data),
                self._upload_config.network_operation_timeout_s()
            )
        except asyncio.TimeoutError:
            self._log_manager.warning("Presigned URL request timed out")
            raise
        return response["upload_url"]

    # Parses a presigned HTTPS URL without modifying its signed path or query.
    def _parse_https_url(self, url):
        prefix = "https://"
        if not url.startswith(prefix):
            raise ValueError("Only HTTPS upload URLs are supported")
        remainder = url[len(prefix):]
        path_start = remainder.find("/")
        if path_start == -1:
            host = remainder
            path = "/"
        else:
            host = remainder[:path_start]
            path = remainder[path_start:]
        return host, path

    async def abort_upload(self):
        if self._upload_task:
            self._log_manager.warning("Stopping current upload before recording")
            self._upload_task.cancel()
            try:
                # Wait until the upload has closed its file and TLS connection.
                await self._upload_task
            except asyncio.CancelledError:
                pass
            finally:
                self._upload_task = None
            self._log_manager.info("Current upload stopped before recording")
            return True
        return False