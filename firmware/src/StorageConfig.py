class StorageConfig:
    def __init__(self):
        self._vid_dir = "/sdcard/motion_capture"
        self._vid_prefix = "video_"
        self._vid_suffix = ".mjpeg"
        self._init_file_num = -1

    def vid_dir(self):
        return self._vid_dir

    def vid_prefix(self):
        return self._vid_prefix

    def vid_suffix(self):
        return self._vid_suffix

    def init_file_num(self):
        return self._init_file_num
