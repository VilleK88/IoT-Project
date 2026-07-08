from src.NetworkConfig import NetworkConfig
import network
import time
import ntptime

class NetworkManager:
    # Initializes the network manager.
    def __init__(self):
        config = NetworkConfig()
        self._ssid = config.ssid()
        self._key = config.key()

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
        print("WiFi connected:", self._wlan.ifconfig())

    def sync_time(self):
        print("Updating date and time...")
        ntptime.settime()
        print("Date and time updated")
        print(time.localtime())