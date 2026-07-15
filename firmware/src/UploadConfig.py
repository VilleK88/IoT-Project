class UploadConfig:
    def __init__(self):
        self._times = [
            [0, 0], [12, 0]
        ]
        self._settings = [
            ["Instantly", True], ["Hourly", False],
            ["Twice per day", False],
            ["Once per day", False]
        ]
        self._upload_time_ms = 60000  # 60 seconds

    def settings(self):
        return self._settings

    def current_setting(self):
        for item in self._settings:
            if item[1]:
                return item[0]
        return None

    def change_settings(self, option):
        for item in self._settings:
            item[1] = (item[0] == option)

    def times(self):
        return self._times

    def upload_time_ms(self):
        return self._upload_time_ms