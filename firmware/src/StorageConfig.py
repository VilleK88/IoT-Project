class StorageConfig:
    def __init__(self):
        self._vid_dir = "/sdcard/motion_capture"
        self._vid_prefix_pag = "video_pag"
        self._video_prefix_lepton = "video_lepton"
        self._vid_suffix = ".mjpeg"
        self._init_file_num = -1

        self._logs_dir = "/sdcard/logs"

        # Logical SD-card allocation.
        self._video_quota_percent = 85
        self._log_quota_percent = 10

        # Remaining 5% is intentionally left unsued as safety margin.

        # Maximum size of one individual log file before rotating.
        self._max_log_file_size = 256 * 1024  # 256 KiB

    def vid_dir(self):
        return self._vid_dir

    def video_prefix_pag(self):
        return self._vid_prefix_pag

    def video_prefix_lepton(self):
        return self._video_prefix_lepton

    def vid_suffix(self):
        return self._vid_suffix

    def init_file_num(self):
        return self._init_file_num

    def logs_dir(self):
        return self._logs_dir

    def video_quota_percent(self):
        return self._video_quota_percent

    def log_quota_percent(self):
        return self._log_quota_percent

    def max_log_file_size(self):
        return self._max_log_file_size