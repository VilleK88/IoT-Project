class MotionConfig:
    def __init__(self):
        self._trig_thresh = 10  # Motion detection threshold 5
        self._bg_upd_frames = 50  # Frames between background updates
        self._bg_upd_blend = 128  # Background blend factor (0-255)
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

    def trig_thresh(self):
        return self._trig_thresh

    def bg_upd_frames(self):
        return self._bg_upd_frames

    def bg_upd_blend(self):
        return self._bg_upd_blend

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
