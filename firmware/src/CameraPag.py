from src.CameraBase import Camera
import csi
import image
import time
import asyncio
import gc

class CameraPag(Camera):
    def __init__(self, log_manager):
        super().__init__()
        self.name = "PAG7936"

        self._log_manager = log_manager

        # Initialize the PAG7936 RGB camera first.
        # It continuously supplies 640x400 frames to the circular prebuffer
        # and switches to 1280x800 when event recording begins.
        self.csi0 = csi.CSI(stream=True)  # Create a new CSI camera object.
        self.csi0.reset()  # Initialize and reset the connected camera sensor.
        self.csi0.pixformat(csi.RGB565)
        self.csi0.framesize(csi.VGA) # PAG7936 output: 640x400

        self.csi0.auto_gain(True)
        self.csi0.auto_exposure(True)
        self.csi0.auto_whitebal(True)  # Enable automatic white balance for improved image quality.

        #self.csi0.vflip(True)
        #self.csi0.auto_rotation(True)

        self._current_frame = (
            self.csi0.snapshot(time=self.cam_config.pag_stabilization_ms())
        )  # Let new settings take effect.

        # Reusable 1280x800 RGB565 frame used to scale 640x400 prebuffer
        # frames without allocating a new large image for every frame.
        # Allocate it before the circular buffer starts fragmenting the heap.
        self._scaled_frame = image.Image(
            self.cam_config.recording_width_pag(),
            self.cam_config.recording_height_pag(),
            csi.RGB565
        )

        self.filename_pag = None
        self.video_pag = None
        self.saved_frames = 0
        self.live_frames_pag = 0

        self._tools.print_memory_status("After PAG7936 init")

    def write_to_pag(self, frame):
        try:
            self.video_pag.write(frame)
        except Exception as error:
            self._log_manager.error("SD card write failed: {}".format(error))
            raise

    def record_frame(self):
        self._current_frame = self.csi0.snapshot()
        self.write_to_pag(self._current_frame)
        self.saved_frames += 1

    # Writes the buffered frames to the MJPEG file.
    # New RGB frames are captured while the prebuffer is written
    # to reduce the gap before live recording.
    def write_prebuffer_with_catchup_pag(self):
        last_live_frame_time_pag = time.ticks_ms()

        self.saved_frames = 0

        # Retrieve the buffered frames in chronological order.
        prebuf_frames_pag, self._buffer_index = (
            self.get_ordered_buf_frames(self._buffer, self._buffer_index)
        )

        # Stores frames captured while the pre-buffer is being written.
        # These frames are appended afterwards to reduce the recording gap.
        catchup_frames_pag = []

        # Write the buffered frames to the MJPEG file.
        for frame in prebuf_frames_pag:
            scaled_frame = self.scale_frame(frame)
            self.write_to_pag(scaled_frame)
            self.saved_frames += 1

            # Periodically capture a new RGB frame while writing to
            # compensate for the time spent saving the prebuffer.
            now = time.ticks_ms()
            if time.ticks_diff(now, last_live_frame_time_pag) >= self._frame_interval_ms:
                self._current_frame = self.csi0.snapshot()
                catchup_frames_pag.append(self._current_frame.copy())
                last_live_frame_time_pag = now

        # Append the frames captured during the pre-buffer write so the
        # transition from buffered video to live recording is as seamless as possible.
        for frame in catchup_frames_pag:
            scaled_frame = self.scale_frame(frame)
            self.write_to_pag(scaled_frame)
            self.saved_frames += 1

    def scale_frame(self, frame):
        self._scaled_frame.draw_image(frame, x_scale=2.0, y_scale=2.0)
        return self._scaled_frame

    # Periodically captures PAG7936 RGB frames into the circular RAM buffer.
    async def update_frame_buffer_pag(self):
        while True:
            self._current_frame = await self._snapshot_async(self.csi0)
            # Store a copy of the current frame in the circular buffer.
            # A copy is required because snapshot() reuses the same image buffer.
            self._buffer_index = (
                self._save_frame(
                    self._current_frame.copy(),
                    self._buffer,
                    self._buffer_index,
                )
            )
            if self._buffer_index == 0:
                self._ring_buf_fil_count += 1
            # Yield control until the next prebuffer frame is due.
            await asyncio.sleep_ms(self._buf_config.frame_interval_ms())

    def prepare_video(self, file_manager):
        # Create a new MJPEG file and prepare the camera for recording.
        self.filename_pag, self.video_pag = self.create_motion_video(
            file_manager,
            self._storage_config.video_prefix_pag(),
            self.cam_config.recording_width_pag(),
            self.cam_config.recording_height_pag(),
        )

    def finalize_video(self, file_manager):
        self.video_pag.close()
        duration_ms = self.saved_frames * self.frame_interval_ms()
        file_manager.patch_mjpeg_timing(
            self.filename_pag,
            self.saved_frames,
            duration_ms
        )
        file_manager.patch_mjpeg_index(self.filename_pag)

    def start_recording_mode(self):
        self.csi0.framesize(csi.HD)

    def stop_recording_mode(self):
        self.csi0.framesize(csi.VGA)

    def buffer(self):
        return self._buffer

    def buffer_index(self):
        return self._buffer_index

    def last_frame_time(self):
        return self._last_frame_time

    def frame_interval_ms(self):
        return self._frame_interval_ms

    def ring_buffer_fill_count(self):
        return self._ring_buf_fil_count