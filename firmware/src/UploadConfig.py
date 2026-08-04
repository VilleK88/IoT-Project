class UploadConfig:
    def __init__(self):
        self._upload_time_ms = 60000  # 60 seconds

    def upload_time_ms(self):
        return self._upload_time_ms