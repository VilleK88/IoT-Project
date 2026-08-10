class NetworkConfig:
    def __init__(self):
        self._SSID = ""
        self._KEY = ""
        self._url_endpoint = ""

    def ssid(self):
        return self._SSID

    def key(self):
        return self._KEY

    def url_endpoint(self):
        return self._url_endpoint