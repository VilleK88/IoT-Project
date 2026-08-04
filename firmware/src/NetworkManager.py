from src.NetworkConfig import NetworkConfig
from src.UploadConfig import UploadConfig
from src.Tools import Tools
import network
import time
import ntptime
import requests
import os
import asyncio

class NetworkManager:
    # Initializes the network manager.
    def __init__(self, file_manager):
        self._tools = Tools()
        self._file_manager = file_manager
        self._upload_config = UploadConfig()

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

        while not self._wlan.isconnected():
            print('Trying to connect to "{:s}"...'.format(self._ssid))
            time.sleep_ms(1000)

        # A valid IP address should now be assigned by DHCP.
        #print("WiFi connected:", self._wlan.ifconfig())
        print("WiFi connected")

    def _sync_time(self):
        ntptime.settime()
        print("Date and time updated:", time.localtime())

    async def upload_task(self):
        # Allow both camera interfaces and the first prebuffer cycle to stabilize.
        await asyncio.sleep_ms(10_000)
        while True:
            await self._upload_mjpeg_files()
            await asyncio.sleep_ms(self._upload_config.upload_time_ms())

    async def _upload_mjpeg_files(self):
        files = self._file_manager.if_files()
        if files:
            for file in files:
                self._tools.print_memory_status("Memory before upload")
                upload_succeeded = await self.upload_mjpeg(file)
                if upload_succeeded:
                    self._file_manager.delete_file(file)
                    print(f"File deleted {file}")
                # Give the network stack time to release TLS resources.
                await asyncio.sleep_ms(2000)

    # Uploads an MJPEG file to AWS S3 using a presigned URL.
    async def upload_mjpeg(self, filename):
        self._tools.cleanup_memory()
        print("Waiting before upload")
        # Request a presigned S3 upload URL and separate it into
        # the hostname and request path required for the HTTP request.
        upload_url = self._get_upload_url()
        host, path = self._parse_https_url(upload_url)
        # Read the file size for the HTTP Content-Length header.
        file_size = os.stat(filename)[6]
        print("Uploading:", filename)
        print("File size:", file_size)

        reader = None
        writer = None

        try:
            print("Before async TLS connection")
            reader, writer = await asyncio.open_connection(host, 443, ssl=True)
            print("Async TLS connection opened")
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
            next_progress_print = 1024 * 1024
            # Stream the file directly from storage to S3 in blocks
            # instead of loading the complete MJPEG file into RAM.
            print("Starting file transfer")
            with open(filename, "rb") as file:
                while True:
                    chunk = file.read(4096)  # Tested options: 4096, 8192, 16384, 32768
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
                        next_progress_print += 1024 * 1024

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

            print("MJPEG upload successful")
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

    # Requests a temporary S3 upload URL from AWS.
    def _get_upload_url(self):
        response = requests.post(
            self._network_config.url_endpoint(),
            json={}
        )

        if response.status_code != 200:
            raise OSError("Upload URL request failed: {}".format(response.status_code))

        data = response.json()
        return data["upload_url"]

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

    # Writes the complete byte buffer to a stream.
    # A socket write may send fewer bytes than requested, so the remaining
    # bytes must be written until the whole buffer has been trasferred.
    def _write_all(self, stream, data):
        offset = 0
        while offset < len(data):
            written = stream.write(data[offset:])
            if written is None or written <= 0:
                raise OSError("Socket write failed")
            offset += written