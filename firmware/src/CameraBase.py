from src.CameraConfig import CameraConfig
from src.MotionConfig import MotionConfig
from src.BufferConfig import BufferConfig
from src.UploadConfig import UploadConfig
from src.StorageConfig import StorageConfig
from src.Tools import Tools
import asyncio
import time

class Camera:
    def __init__(self):
        self.name = "Generic camera"

        # Feature configuration
        self.cam_config = CameraConfig()
        self._mot_conf = MotionConfig()
        self._buf_config = BufferConfig()
        self._upload_config = UploadConfig()
        self._storage_config = StorageConfig()
        self._tools = Tools()

        # Circular prebuffer state
        self._buffer = [None] * self._buf_config.buf_size()
        self._buffer_index = 0
        self._last_frame_time = 0
        self._frame_interval_ms = self._buf_config.frame_interval_ms()
        self._ring_buf_fil_count = 0

    async def _snapshot_async(self, camera):
        while True:
            img = camera.snapshot(blocking=False)
            if img is not None:
                return img
            await asyncio.sleep_ms(0)

    # Returns the buffered frames in chronological order.
    def get_ordered_buf_frames(self, this_buffer, this_index):
        frames = []
        # Start from the oldest frame in the circular buffer.
        # _buf_index always points to the next position that will be overwritten.
        for i in range(self._buf_config.buf_size()):
            # Wrap around to the beginning of the buffer when the end is reached.
            index = (this_index + i) % self._buf_config.buf_size()
            frame = this_buffer[index]
            # Ignore unused slots until the buffer has been filled for the first time.
            if frame is not None:
                frames.append(frame)
        return frames, this_index

    # Stores a frame in the circular buffer and advances the write index.
    def _save_frame(self, frame, this_buffer, this_index):
        # Store the newest frame at the current write position.
        this_buffer[this_index] = frame
        # Advance the write index and wrap back to the beginning when the
        # end of the circular buffer is reached.
        this_index = (this_index + 1) % self._buf_config.buf_size()
        # The buffer has been completely filled once the write index wraps
        # back to the beginning. From this point onward, the oldest frames
        # will be overwritten by newer ones.
        return this_index

    # Clears the circular frame buffer after recording.
    def clear_frame_buffer(self, this_buffer):
        for i in range(self._buf_config.buf_size()):
            this_buffer[i] = None
        this_index = 0
        this_frame_time = time.ticks_ms()
        return this_index, this_frame_time