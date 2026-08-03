class MotionConfig:
    def __init__(self):
        self._chk_mot_ms = 200 # 200 = 5 times per second
        self._init_file_num = -1  # Initial file counter value
        self._motion_timeout_ms = 5000  # 5 seconds

    def chk_mot_ms(self):
        return self._chk_mot_ms

    def init_file_num(self):
        return self._init_file_num

    def motion_timeout_ms(self):
        return self._motion_timeout_ms