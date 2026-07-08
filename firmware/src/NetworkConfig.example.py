class NetworkConfig:
    def __init__(self):
        self._SSID = ""
        self._KEY = ""

    def ssid(self):
        return self._SSID

    def key(self):
        return self._KEY