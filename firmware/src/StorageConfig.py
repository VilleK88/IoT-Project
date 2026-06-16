class StorageConfig:
    def __init__(self):
        self._vid_dir = "/sdcard/motion_capture"
        self._img_dir = "/sdcard/motion_images"
        self._temp_dir = "/sdcard/temp"
        self._vid_prefix = "video_"
        self._img_prefix = "pic_"
        self._vid_suffix = ".mjpeg"
        self._img_suffix = ".jpg"
        self._init_file_num = -1

    def vid_dir(self):
        return self._vid_dir

    def img_dir(self):
        return self._img_dir

    def temp_dir(self):
        return self._temp_dir

    def vid_prefix(self):
        return self._vid_prefix

    def img_prefix(self):
        return self._img_prefix

    def vid_suffix(self):
        return self._vid_suffix

    def img_suffix(self):
        return self._img_suffix

    def init_file_num(self):
        return self._init_file_num
