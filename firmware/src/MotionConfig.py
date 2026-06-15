class MotionConfig:
    def __init__(self):
        self._trigger_threshold = 15
        self._bg_update_frames = 50
        self._bg_update_blend = 128
        self._record_check_interval_ms = 3000
        self._post_record_cooldown_ms = 1000

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
