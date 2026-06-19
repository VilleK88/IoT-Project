class BufferConfig:
    def __init__(self):
        # How many seconds of pre-motion frames should be kept in RAM
        self._buf_sec = 10
        # How many frames per second are stored into the RAM buffer
        self._buf_fps = 15
        # Total number of frames stored in the circular buffer
        # Example: 10 seconds * 2 FPS = 20 buffered frames
        self._buf_size = self._buf_sec * self._buf_fps

    def buf_sec(self):
        return self._buf_sec

    def buf_fps(self):
        return self._buf_fps

    def buf_size(self):
        return self._buf_size
