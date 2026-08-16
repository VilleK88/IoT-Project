from src.NetworkConfig import NetworkConfig
from src.UploadConfig import UploadConfig
from src.TimeManager import TimeManager
from src.CameraConfig import CameraConfig
from src.Tools import Tools
import network
import time
import ntptime
import requests
import os
import asyncio
import json

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

    def initialize(self):
        self.connect()
        self._sync_time()

    # Connects the device to the configured WiFi network.
    def connect(self):
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
        print("Wi-Fi connected")

    async def reconnect(self):
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

    async def radio_power_cycle(self):
        print("Power cycling Wi-Fi interface")
        self._log_manager.info("Power cycling Wi-Fi interface")
        self._wlan.active(False)
        await asyncio.sleep(self._upload_config.radio_restart_delay_s())
        self._wlan.active(True)
        return await self.reconnect()

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
            if self._wlan.isconnected():
                await self._upload_mjpeg_files()
            else:
                reconnected = await self.reconnect()
                if not reconnected:
                    await self.radio_power_cycle()
            await asyncio.sleep_ms(self._upload_config.upload_time_ms())

    async def _upload_mjpeg_files(self):
        files = self._file_manager.get_files()
        if files:
            for file in files:
                self._tools.print_memory_status("Memory before upload")
                upload_succeeded = await self.upload_mjpeg(file)
                if upload_succeeded:
                    self._file_manager.delete_file(file)
                    print(f"File deleted {file}")
                    self._log_manager.info(f"File deleted {file}")
                    self._tools.cleanup_memory()
                    self._tools.print_memory_status("Memory after successful upload cleanup")
                # Give the network stack time to release TLS resources.
                await asyncio.sleep_ms(self._upload_config.post_upload_delay_ms())

    # Uploads an MJPEG file to AWS S3 using a presigned URL.
    async def upload_mjpeg(self, filename):
        self._tools.cleanup_memory()
        self._tools.print_memory_status("Memory after cleanup -> next uploading")
        metadata = self._file_manager.get_video_metadata(filename)
        data = {
            "camera_id": self._camera_config.camera_id(),
            "event_id": metadata["event_id"],
            "sensor": metadata["sensor"]
        }
        # Request a presigned S3 upload URL and separate it into
        # the hostname and request path required for the HTTP request.
        upload_url = await self._get_upload_url(data)
        host, path = self._parse_https_url(upload_url)
        # Read the file size for the HTTP Content-Length header.
        file_size = os.stat(filename)[6]
        print("Uploading:", filename)
        print("File size:", file_size)

        reader = None
        writer = None

        try:
            reader, writer = await asyncio.open_connection(
                host, self._upload_config.https_port(), ssl=True
            )
            # Build the HTTP PUT request header.
            # The presigned URL already contains the authentication
            # parameters required by S3.
            request_header= (
                "PUT {} HTTP/1.1\r\n"
                "Host: {}\r\n"
                "Content-Length: {}\r\n"
                "Connection: close\r\n"
                "\r\n"
            ).format(path, host, file_size)
            # Send the complete request header before transmitting
            # the MJPEG file contents
            writer.write(request_header.encode())
            await writer.drain()
            upload_start_time = time.ticks_ms()

            bytes_sent = 0
            next_progress_print = self._upload_config.progress_interval_bytes()
            # Stream the file directly from storage to S3 in blocks
            # instead of loading the complete MJPEG file into RAM.
            with open(filename, "rb") as file:
                while True:
                    chunk = file.read(self._upload_config.upload_chunk_size())  # Tested options: 4096, 8192, 16384, 32768
                    # An empty read indicates that the end of the file
                    # has been reached.
                    if not chunk:
                        break
                    # Ensure the complete block is written before reading
                    writer.write(chunk)
                    await writer.drain()
                    bytes_sent += len(chunk)

                    if bytes_sent >= next_progress_print:
                        print("Uploaded KiB:", bytes_sent // 1024)
                        next_progress_print += self._upload_config.progress_interval_bytes()

            # Read the first line of the HTTP response, for example:
            # HTTP/1.1 200 OK
            status_line = await reader.readline()
            # A missing response usually means that the connection was
            # closed before S3 returned an HTTP status.
            if not status_line:
                raise OSError("No response received from S3")
            print("S3 response:", status_line)
            # A successful S3 PUT upload returns HTTP status 200.
            # Read and print the remaining response only when the upload fails.
            if b" 200 " not in status_line:
                #response_body = tls_sock.read()
                response_body = await reader.read()
                print("S3 error response:", response_body)
                raise OSError("MJPEG upload failed")

            self._log_manager.info(f"{filename} uploaded successfully")
            # Calculate the total upload duration and average transfer speed.
            upload_duration_ms = time.ticks_diff(time.ticks_ms(), upload_start_time)
            print("Upload duration ms:", upload_duration_ms)
            print("Upload speed KiB/s:", (file_size * 1000) // upload_duration_ms // 1024)
            return True

        except Exception as error:
            print("MJPEG upload error:", error)
            return False

        finally:
            if writer is not None:
                try:
                    writer.close()
                    await writer.wait_closed()
                except Exception as error:
                    print("Writer close error:", error)

    # Sends a JSON POST request over HTTPS and returns the JSON response.
    async def _post_json(self, url, data):
        host, path = self._parse_https_url(url)

        # Convert the Python object into a JSON request body.
        body = json.dumps(data)

        reader = None
        writer = None

        try:
            reader, writer = await asyncio.open_connection(
                host, self._upload_config.https_port(), ssl=True
            )

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

            if not status_line:
                raise OSError("No response received")

            if b" 200 " not in status_line:
                raise OSError(
                    "HTTP POST failed: {}".format(status_line)
                )

            # Skip HTTP response headers.
            while True:
                line = await reader.readline()

                if line == b"\r\n":
                    break

            # Read and decode the JSON response body.
            response_body = await reader.read()
            return json.loads(response_body)

        except Exception as error:
            print("POST error:", error)
            raise

        finally:
            if writer is not None:
                try:
                    writer.close()
                    await writer.wait_closed()
                except Exception as error:
                    print("Writer close error:", error)

    # Requests a temporary S3 upload URL from AWS.
    async def _get_upload_url(self, data):
        response = await self._post_json(self._network_config.url_endpoint(), data)
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