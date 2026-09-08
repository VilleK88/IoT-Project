class UploadConfig:
    def __init__(self):
        self._upload_time_ms = 60000  # 60 seconds

        self._backoff_s = (1, 2, 4, 8, 16, 32, 60)

        self._reconnect_timeout_ms = 10_000
        self._reconnect_poll_ms = 100
        self._radio_restart_delay_s = 1

        self._startup_delay_ms = 10_000
        self._post_upload_delay_ms = 2_000

        self._https_port = 443
        self._upload_chunk_size = 4096 # 262144

        self._connect_poll_ms = 1000

        self._connect_max_attempts = 10

        self._upload_progress_timeout_ms = 10000
        self._stream_timeout_s = 10
        self._response_timeout_s = 10
        self._memory_log_interval_ms = 10_000

    def upload_time_ms(self):
        return self._upload_time_ms

    def backoff_s(self):
        return self._backoff_s

    def reconnect_timeout_ms(self):
        return self._reconnect_timeout_ms

    def reconnect_poll_ms(self):
        return self._reconnect_poll_ms

    def radio_restart_delay_s(self):
        return self._radio_restart_delay_s

    def startup_delay_ms(self):
        return self._startup_delay_ms

    def post_upload_delay_ms(self):
        return self._post_upload_delay_ms

    def https_port(self):
        return self._https_port

    def upload_chunk_size(self):
        return self._upload_chunk_size

    def connect_poll_ms(self):
        return self._connect_poll_ms

    def connect_max_attempts(self):
        return self._connect_max_attempts

    def upload_progress_timeout_ms(self):
        return self._upload_progress_timeout_ms

    def stream_timeout_s(self):
        return self._stream_timeout_s

    def response_timeout_s(self):
        return self._response_timeout_s

    def memory_log_interval_ms(self):
        return self._memory_log_interval_ms