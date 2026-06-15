class StorageConfig:
    def __init__(self):
        self._video_folder = "/sdcard/motion_capture"
        self._image_folder = "/sdcard/motion_images"
        self._video_prefix = "video_"
        self._image_prefix = "pic_"
        self._video_suffix = ".mjpeg"
        self._image_suffix = ".jpg"
        self._initial_file_number = -1

    def video_folder(self):
        return self._video_folder

    def image_folder(self):
        return self._image_folder

    def video_prefix(self):
        return self._video_prefix

    def image_prefix(self):
        return self._image_prefix

    def video_suffix(self):
        return self._video_suffix

    def image_suffix(self):
        return self._image_suffix

    def initial_file_number(self):
        return self._initial_file_number
