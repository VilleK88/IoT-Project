class BufferConfig:
    def __init__(self):
        # How many seconds of pre-motion frames should be kept in RAM
        self._buffer_seconds = 10
        # How many frames per second are stored into the RAM buffer
        self._buffer_fps = 2
        # Total number of frames stored in the circular buffer
        # Example: 10 seconds * 2 FPS = 20 buffered frames
        self._buffer_size = self._buffer_seconds * self._buffer_fps

    def buffer_seconds(self):
        return self._buffer_seconds

    def buffer_fps(self):
        return self._buffer_fps

    def buffer_size(self):
        return self._buffer_size
