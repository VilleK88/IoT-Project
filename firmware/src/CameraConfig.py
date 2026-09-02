class CameraConfig:
    def __init__(self):
        self._camera_id = "camera_001"

        self._buf_width_pag = 640
        self._buf_height_pag = 400
        self._recording_width_pag = 1280
        self._recording_height_pag = 800

        self._width_lepton = 160
        self._height_lepton = 120

        self._max_recording_time_ms = 1 * 60 * 1000  # Maximum recording duration 1 minutes.

        self._pag_stabilization_ms = 2000
        self._lepton_stabilization_ms = 5000

    def buf_width_pag(self):
        return self._buf_width_pag

    def buf_height_pag(self):
        return self._buf_height_pag

    def recording_width_pag(self):
        return self._recording_width_pag

    def recording_height_pag(self):
        return self._recording_height_pag

    def width_lepton(self):
        return self._width_lepton

    def height_lepton(self):
        return self._height_lepton

    def max_recording_time_ms(self):
        return self._max_recording_time_ms

    def pag_stabilization_ms(self):
        return self._pag_stabilization_ms

    def lepton_stabilization_ms(self):
        return self._lepton_stabilization_ms

    def camera_id(self):
        return self._camera_id