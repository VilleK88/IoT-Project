class MotionConfig:
    def __init__(self):
        self._trigger_threshold = 15
        self._bg_update_frames = 50
        self._bg_update_blend = 128
        self._record_check_interval_ms = 3000
        self._post_record_cooldown_ms = 1000
        self._main_loop_cooldown_ms = 1000
        self._debug_record_duration_seconds = 10
        self._milliseconds_per_second = 1000
        self._stabilization_delay_ms = 2000
        self._stabilization_frames = 100
        self._stabilization_frame_delay_ms = 20
        self._initial_file_number = -1

    def trigger_threshold(self):
        return self._trigger_threshold

    def bg_update_frames(self):
        return self._bg_update_frames

    def bg_update_blend(self):
        return self._bg_update_blend

    def record_check_interval_ms(self):
        return self._record_check_interval_ms

    def post_record_cooldown_ms(self):
        return self._post_record_cooldown_ms

    def main_loop_cooldown_ms(self):
        return self._main_loop_cooldown_ms

    def debug_record_duration_seconds(self):
        return self._debug_record_duration_seconds

    def milliseconds_per_second(self):
        return self._milliseconds_per_second

    def stabilization_delay_ms(self):
        return self._stabilization_delay_ms

    def stabilization_frames(self):
        return self._stabilization_frames

    def stabilization_frame_delay_ms(self):
        return self._stabilization_frame_delay_ms

    def initial_file_number(self):
        return self._initial_file_number
