from src.NetworkConfig import NetworkConfig
from src.UploadConfig import UploadConfig
import network
import time
import ntptime

import requests
import os
import socket
import ssl

class NetworkManager:
    # Initializes the network manager.
    def __init__(self, file_manager):
        self._file_manager = file_manager
        self._upload_config = UploadConfig()

        self._network_config = NetworkConfig()
        self._ssid = self._network_config.ssid()
        self._key = self._network_config.key()

        self._wlan = network.WLAN(network.STA_IF)
        self._wlan.active(True)

        self._last_upload_check_time_ms = time.ticks_ms()


    def initialize(self):
        self.connect()
        self.sync_time()
        self.upload_mjpeg_files()

    # Connects the device to the configured WiFi network.
    def connect(self):
        self._wlan.connect(self._ssid, self._key)

        while not self._wlan.isconnected():
            print('Trying to connect to "{:s}"...'.format(self._ssid))
            time.sleep_ms(1000)

        # A valid IP address should now be assigned by DHCP.
        #print("WiFi connected:", self._wlan.ifconfig())
        print("WiFi connected")

    def sync_time(self):
        print("Updating date and time...")
        ntptime.settime()
        print("Date and time updated")
        print(time.localtime())


    def scheduled_upload(self):
        option = self._upload_config.current_setting()
        year, month, day, hour, minute, second, weekday, yearday = time.localtime()
        if option == "Hourly":
            if minute == 0 and second == 0:
                self.upload_mjpeg_files()
        elif option == "Twice per day":
            for item in self._upload_config.times():
                if item[0] == hour and item[1] == minute:
                    self.upload_mjpeg_files()
        elif option == "Once per day":
            if self._upload_config.times()[0][0] == hour and self._upload_config.times()[0][1] == minute:
                self.upload_mjpeg_files()
        else:
            print("Unknown command!")

    def should_upload(self):
        now = time.ticks_ms()
        if time.ticks_diff(now, self._last_upload_check_time_ms) >= self._upload_config.upload_time_ms():
            self._last_upload_check_time_ms = now
            return True
        return False


    def upload_mjpeg_files(self):
        files = self._file_manager.if_files()
        if files:
            for file in files:
                filename = self._file_manager.motion_capture_dir() + "/" + file
                if self.upload_mjpeg(filename):
                    #self._file_manager.delete_file(filename)
                    print(f"File deleted {filename}")

    # Uploads an MJPEG file to AWS S3 using a presigned URL.
    def upload_mjpeg(self, filename):
        # Request a presigned S3 upload URL and separate it into
        # the hostname and request path required for the HTTP request.
        upload_url = self.get_upload_url()
        host, path = self.parse_https_url(upload_url)
        # Read the file size for the HTTP Content-Length header.
        file_size = os.stat(filename)[6]
        print("Uploading:", filename)
        print("File size:", file_size)
        sock = None
        tls_sock = None

        try:
            # Resolve the S3 hostname and establish a TCP connection
            # to the HTTPS port.
            address = socket.getaddrinfo(host, 443)[0][-1]
            sock = socket.socket()
            sock.connect(address)

            # Encrypt the TCP connection with TLS.
            # server_hostname enables SNI so that S3 provides the
            # certificate matching the requested hostname
            tls_sock = ssl.wrap_socket(sock, server_hostname=host)

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
            self.write_all(tls_sock, request_header.encode())
            upload_start_time = time.ticks_ms()

            # Stream the file directly from storage to S3 in blocks
            # instead of loading the complete MJPEG file into RAM.
            with open(filename, "rb") as file:
                while True:
                    chunk = file.read(16384)  # Tested options: 4096, 8192, 16384, 32768
                    # An empty read indicates that the end of the file
                    # has been reached.
                    if not chunk:
                        break
                    # Ensure the complete block is written before reading
                    # and sending the next one.
                    self.write_all(tls_sock, chunk)

            # Read the first line of the HTTP response, for example:
            # HTTP/1.1 200 OK
            status_line = tls_sock.readline()
            # A missing response usually means that the connection was
            # closed before S3 returned an HTTP status.
            if not status_line:
                raise OSError("No response received from S3")
            print("S3 response:", status_line)
            # A successful S3 PUT upload returns HTTP status 200.
            # Read and print the remaining response only when the upload fails.
            if b" 200 " not in status_line:
                response_body = tls_sock.read()
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
            # Always close the active network socket, including when
            # connecting, sending, or receiving raises an exception.
            if tls_sock is not None:
                tls_sock.close()
            elif sock is not None:
                sock.close()

    # Requests a temporary S3 upload URL from AWS.
    def get_upload_url(self):
        response = requests.post(
            self._network_config.url_endpoint(),
            json={}
        )

        if response.status_code != 200:
            raise OSError("Upload URL request failed: {}".format(response.status_code))

        data = response.json()
        return data["upload_url"]

    # Parses a presigned HTTPS URL without modifying its signed path or query.
    def parse_https_url(self, url):
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
    def write_all(self, stream, data):
        offset = 0

        while offset < len(data):
            written = stream.write(data[offset:])

            if written is None or written <= 0:
                raise OSError("Socket write failed")

            offset += written