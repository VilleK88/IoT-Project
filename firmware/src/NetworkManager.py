from src.NetworkConfig import NetworkConfig
import network
import time
import ntptime

import requests
import os
import socket
import ssl

class NetworkManager:
    # Initializes the network manager.
    def __init__(self):
        self.config = NetworkConfig()
        self._ssid = self.config.ssid()
        self._key = self.config.key()

        self._wlan = network.WLAN(network.STA_IF)
        self._wlan.active(True)

    def initialize(self):
        self.connect()
        self.sync_time()

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

    # Uploads an MJPEG file to AWS S3 using a presigned URL.
    def upload_mjpeg(self, filename):
        upload_url = self.get_upload_url()
        host, path = self.parse_https_url(upload_url)
        file_size = os.stat(filename)[6]

        print("Uploading:", filename)
        print("File size:", file_size)

        sock = None
        tls_sock = None

        try:
            # Resolve the S3 hostname and open a TCP connection.
            address = socket.getaddrinfo(host, 443)[0][-1]
            sock = socket.socket()
            sock.connect(address)

            # Wrap the TCP socket in TLS.
            # server_hostname enables SNI so S3 presents the correct certificate.
            tls_sock = ssl.wrap_socket(sock, server_hostname=host)

            # Build the HTTP PUT request header.
            request_header= (
                "PUT {} HTTP/1.1\r\n"
                "Host: {}\r\n"
                "Content-Length: {}\r\n"
                "Connection: close\r\n"
                "\r\n"
            ).format(path, host, file_size)

            self.write_all(tls_sock, request_header.encode())

            upload_start_time = time.ticks_ms()

            # Stream the file to S3 in small blocks.
            with open(filename, "rb") as file:
                while True:
                    chunk = file.read(16384)  # 4096, 8192, 16384, 32768

                    if not chunk:
                        break

                    self.write_all(tls_sock, chunk)

            # Read the first HTTP response line, for example
            # HTTP/1.1 200 OK
            status_line = tls_sock.readline()

            if not status_line:
                raise OSError("No response received from S3")

            print("S3 response:", status_line)

            if b" 200 " not in status_line:
                response_body = tls_sock.read()
                print("S3 error response:", response_body)
                raise OSError("MJPEG upload failed")

            print("MJPEG upload successful")

            upload_duration_ms = time.ticks_diff(time.ticks_ms(), upload_start_time)

            print("Upload duration ms:", upload_duration_ms)
            print("Upload speed KiB/s:", (file_size * 1000) // upload_duration_ms // 1024)

        finally:
            if tls_sock is not None:
                tls_sock.close()
            elif sock is not None:
                sock.close()

    # Requests a temporary S3 upload URL from AWS.
    def get_upload_url(self):
        response = requests.post(
            self.config.url_endpoint(),
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