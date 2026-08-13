class MotionConfig:
    def __init__(self):
        self._chk_mot_ms = 200 # 200 = 5 times per second
        self._init_file_num = -1  # Initial file counter value
        self._motion_timeout_ms = 5000  # 5 seconds

        self._trigger_threshold = 5
        self._bg_update_frames = 5
        self._bg_update_blend = 128

        self._min_temp_in_celsius = 20.0  # Minimum temperature represented by grayscale value 0.
        self._max_temp_in_celsius = 40.0  # Maximum temperature represented by grayscale value 255.

        self._hist_low_percentile = 0.90
        self._hist_high_percentile = 0.99

    def chk_mot_ms(self):
        return self._chk_mot_ms

    def init_file_num(self):
        return self._init_file_num

    def motion_timeout_ms(self):
        return self._motion_timeout_ms

    def trigger_threshold(self):
        return self._trigger_threshold

    def bg_update_frames(self):
        return self._bg_update_frames

    def bg_update_blend(self):
        return self._bg_update_blend

    def min_temp_in_celsius(self):
        return self._min_temp_in_celsius

    def max_temp_in_celsius(self):
        return self._max_temp_in_celsius

    def hist_low_percentile(self):
        return self._hist_low_percentile

    def hist_high_percentile(self):
        return self._hist_high_percentile