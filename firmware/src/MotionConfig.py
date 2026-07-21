class MotionConfig:
    def __init__(self):
        self._motion_width = 320
        self._motion_height = 240
        self._chk_mot_ms = 200 # 200 = 5 times per second
        self._rec_chk_int_ms = 3000  # Motion recheck interval during recording (ms)
        self._post_rec_cd_ms = 1000  # Cooldown after recording stops (ms)
        self._main_loop_cd_ms = 1000  # Main loop delay (ms)
        self._debug_rec_dur_s = 10  # Debug recording duration (s)
        self._ms_per_s = 1000  # Milliseconds per second
        self._stab_delay_ms = 2000  # Camera stabilization delay (ms)
        self._stab_frames = 100  # Frames used for camera stabilization
        self._stab_frame_delay_ms = 20  # Delay between stabilization frames (ms)
        self._init_file_num = -1  # Initial file counter value
        self._motion_timeout_ms = 5000  # 5 seconds

    def motion_width(self):
        return self._motion_width

    def motion_height(self):
        return self._motion_height

    def chk_mot_ms(self):
        return self._chk_mot_ms

    def rec_chk_int_ms(self):
        return self._rec_chk_int_ms

    def post_rec_cd_ms(self):
        return self._post_rec_cd_ms

    def main_loop_cd_ms(self):
        return self._main_loop_cd_ms

    def debug_rec_dur_s(self):
        return self._debug_rec_dur_s

    def ms_per_s(self):
        return self._ms_per_s

    def stab_delay_ms(self):
        return self._stab_delay_ms

    def stab_frames(self):
        return self._stab_frames

    def stab_frame_delay_ms(self):
        return self._stab_frame_delay_ms

    def init_file_num(self):
        return self._init_file_num

    def motion_timeout_ms(self):
        return self._motion_timeout_ms