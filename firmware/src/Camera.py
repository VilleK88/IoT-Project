from src.MotionConfig import MotionConfig
from src.BufferConfig import BufferConfig
from src.UploadConfig import UploadConfig
from src.Tools import Tools
import mjpeg
import image
import csi
import machine
import time
import asyncio
import imu

class Camera:
    # Initializes the camera system and all runtime resources.
    def __init__(self, storage_config, file_manager, network_manager):
        self._tools = Tools()
        self._tools.print_memory_status("Before camera initialization")

        # External dependencies
        self._storage_config = storage_config
        self._file_manager = file_manager
        self._network_manager = network_manager

        # Feature configuration
        self._mot_conf = MotionConfig()
        self._buf_config = BufferConfig()
        self._upload_config = UploadConfig()

        # Recording state
        self._led = machine.LED("LED_RED")
        self._max_recording_time_ms = 2 * 60 * 1000  # Maximum recording duration 2 minutes.


        # Motion-check timing
        self._last_motion_check_time = time.ticks_ms()

        # Circular RGB prebuffer state
        self._buffer = [None] * self._buf_config.buf_size()
        self._buf_index = 0
        self._last_frame_time = 0
        self._frame_interval_ms = self._buf_config.frame_interval_ms()
        self._ring_buf_fil_count = 0

        # Thermal frame-differencing settings
        self._min_temp_in_celsius = 20.0  # Minimum temperature represented by grayscale value 0.
        self._max_temp_in_celsius = 40.0  # Maximum temperature represented by grayscale value 255.
        self._frame_count = 0
        self._trigger_threshold = 5
        self._bg_update_frames = 5
        self._bg_update_blend = 128

        # Initialize the PAG7936 RGB camera first.
        # It continuously supplies 640x400 frames to the circular prebuffer
        # and switches to 1280x800 when event recording begins.
        self.csi0 = csi.CSI()  # Create a new CSI camera object.
        self.csi0.reset()  # Initialize and reset the connected camera sensor.
        self.csi0.pixformat(csi.RGB565)
        self.csi0.framesize(csi.VGA) # PAG7936 output: 640x400

        self.csi0.auto_gain(True)
        self.csi0.auto_exposure(True)
        self.csi0.auto_whitebal(True)  # Enable automatic white balance for improved image quality.

        self.csi0.vflip(True)
        #self.csi0.auto_rotation(True)

        self._current_frame = self.csi0.snapshot(time=2000)  # Let new settings take effect.

        # Initialize the FLIR Lepton thermal camera second.
        # Use a soft reset so the already initialized PAG7936 remains active.
        self.csi1 = csi.CSI(cid=csi.LEPTON)
        self.csi1.reset(hard=False)  # Soft reset and initialize the sensor
        self.csi1.pixformat(csi.GRAYSCALE)  # Set pixel format to GRAYSCALE
        self.csi1.framesize(csi.QQVGA)  # Native Lepton resolution: 160x120

        self.csi1.auto_rotation(True)

        # Enable radiometric measurement mode and map the grayscale output
        # to the configured temperature range.
        self.csi1.ioctl(csi.IOCTL_LEPTON_SET_MODE, True, True)
        self.csi1.ioctl(csi.IOCTL_LEPTON_SET_RANGE, self._min_temp_in_celsius, self._max_temp_in_celsius)

        # Allow the Lepton to stabilize before capturing the initial
        # background image used by thermal frame differencing.
        self.csi1.snapshot(time=5000)
        self._extra_fb = image.Image(self.csi1.width(), self.csi1.height(), self.csi1.pixformat())
        print("About to save background image...")
        self._extra_fb.draw_image(self.csi1.snapshot())
        print("Saved background image - Now frame differencing!")

        # Reusable 1280x800 RGB565 frame used to scale 640x400 prebuffer
        # frames without allocating a new large image for every frame.
        # Allocate it before the circular buffer starts fragmenting the heap.
        self._scaled_frame = image.Image(1280, 800, csi.RGB565)

        self._tools.print_memory_status("After camera initialization")

    # Returns True when it is time to perform the next motion check.
    async def monitor_motion(self):
        while True:
            if await self.detect_motion_async_lepton():
                print("camera.record_video()")
                self.record_video()
            await asyncio.sleep_ms(self._mot_conf.chk_mot_ms())

    # Records an MJPEG video beginning with the buffered frames
    # followed by live RGB frames.
    def record_video(self):
        self._tools.print_memory_status("Before recording with prebuffer")
        self._tools.cleanup_memory()
        self._tools.print_memory_status("Memory After cleanup")
        # Create a new MJPEG file and prepare the camera for recording.
        filename, video = self.create_motion_video()
        saved_frames = 0
        try:
            # Write the buffered RGB frames before switching the PAG7936 to HD mode.
            print("Before write_prebuffer_with_catchup()")
            saved_frames = self.write_prebuffer_with_catchup(video)
            print("After write_prebuffer_with_catchup()")

            print("Before start_recording_state()")
            self.start_recording_state()
            print("After start_recording_state()")

            last_live_frame_time = time.ticks_ms()
            last_motion_check = time.ticks_ms()
            recording_start_time = time.ticks_ms()
            last_motion_time = time.ticks_ms()
            # Continue recording RGB frames until no motion is detected or the maximum recording time is reached.
            while time.ticks_diff(time.ticks_ms(), recording_start_time) < self._max_recording_time_ms:
                now = time.ticks_ms()
                # Maintain the configured recording frame rate.
                if time.ticks_diff(now, last_live_frame_time) >= self._frame_interval_ms:
                    last_live_frame_time = now
                    img = self.csi0.snapshot()  # Capture the next RGB frame.
                    #print("Captured frame:", img.width(), img.height())
                    self._current_frame = img
                    video.write(img)  # Append the frame to the MJPEG video.
                    saved_frames += 1
                    # Check for movement at the configured interval.
                    if time.ticks_diff(now, last_motion_check) >= self._mot_conf.chk_mot_ms():
                        last_motion_check = now
                        # Reset the no-motion timer whenever movement is detected.
                        if self._detect_motion_lepton():
                            last_motion_time = now
                        # Stop recording after the configured period without movement.
                        elif time.ticks_diff(now, last_motion_time) >= self._mot_conf.motion_timeout_ms():
                            break
        finally:
            video.close() # Always close the MJPEG file, even if recording exits unexpectedly.
            self._led.off()  # Turn off the recording status LED.
            # Update the MJPEG timing so playback matches the original capture rate.
            duration_ms = saved_frames * self._frame_interval_ms
            self._file_manager.patch_mjpeg_timing(filename, saved_frames, duration_ms)
            self._file_manager.patch_mjpeg_index(filename)
            self._tools.print_memory_status("record_video_with_prebuffer done")
            self._tools.cleanup_memory()
            self._tools.print_memory_status("Memory After cleanup")
            self.stop_recording_state()  # Restore the default camera state after recording.

    # Creates a new MJPEG file for motion recording.
    def create_motion_video(self):
        # Build a unique filename using the configured folder, prefix,
        # suffix and the next available video number.
        filename = self._file_manager.build_filename(
            self._storage_config.vid_dir(),
            self._storage_config.vid_prefix(),
            self._storage_config.vid_suffix(),
            self._file_manager.get_video_count()
        )
        # Reserve the next video number for future recordings.
        self._file_manager.increase_video_count()
        print("Recording:", filename)

        print("Before mjpeg.Mjpeg()")
        # Create and return the MJPEG video object.
        #return filename, mjpeg.Mjpeg(filename, width=1280, height=800)
        video = mjpeg.Mjpeg(filename, width=1280, height=800)
        print("After mjpeg.Mjpeg()")
        return filename, video

    # Enables the hardware and camera settings required for recording.
    def start_recording_state(self):
        self.csi0.framesize(csi.HD)  # 1280x800
        print("CSI resolution:", self.csi0.width(), self.csi0.height())
        self._led.on()  # Turn on the recording status LED.

    # Restores the camera state after recording has finished.
    def stop_recording_state(self):
        # Remove any buffered frames so the next recording starts with
        self.clear_frame_buffer()  # a fresh circular buffer.
        self.csi0.framesize(csi.VGA)  # PAG7936 output: 640x400

    # Writes the buffered frames to the MJPEG file.
    # New RGB frames are captured while the prebuffer is written
    # to reduce the gap before live recording.
    def write_prebuffer_with_catchup(self, video):
        last_live_frame_time = time.ticks_ms()
        saved_frames = 0
        print("Getting ordered prebuffer")
        # Retrieve the buffered frames in chronological order.
        prebuf_frames = self.get_ordered_buf_frames()
        print("Writing prebuffer frames")
        # Stores frames captured while the pre-buffer is being written.
        # These frames are appended afterwards to reduce the recording gap.
        catchup_frames = []
        # Write the buffered frames to the MJPEG file.
        for frame in prebuf_frames:
            scaled_frame = self.scale_frame(frame)
            video.write(scaled_frame)
            saved_frames += 1
            # Periodically capture a new RGB frame while writing to
            # compensate for the time spent saving the prebuffer.
            now = time.ticks_ms()
            if time.ticks_diff(now, last_live_frame_time) >= self._frame_interval_ms:
                self._current_frame = self.csi0.snapshot()
                catchup_frames.append(self._current_frame.copy())
                last_live_frame_time = now
        print("Writing catchup frames")
        # Append the frames captured during the pre-buffer write so the
        # transition from buffered video to live recording is as seamless as possible.
        for frame in catchup_frames:
            scaled_frame = self.scale_frame(frame)
            video.write(scaled_frame)
            saved_frames += 1
        return saved_frames

    def scale_frame(self, frame):
        self._scaled_frame.draw_image(frame, x_scale=2.0, y_scale=2.0)
        #print("Scaled:", self._scaled_frame.width(), self._scaled_frame.height())
        return self._scaled_frame

    # Periodically captures PAG7936 RGB frames into the circular RAM buffer.
    async def update_frame_buffer_pag(self):
        while True:
            self._current_frame = await self._snapshot_async(self.csi0)
            # Store a copy of the current frame in the circular buffer.
            # A copy is required because snapshot() reuses the same image buffer.
            self._save_frame(self._current_frame.copy())
            # Yield control until the next prebuffer frame is due.
            await asyncio.sleep_ms(self._buf_config.frame_interval_ms())


    # Stores a frame in the circular buffer and advances the write index.
    def _save_frame(self, frame):
        # Store the newest frame at the current write position.
        self._buffer[self._buf_index] = frame
        # Advance the write index and wrap back to the beginning when the
        # end of the circular buffer is reached.
        self._buf_index = (self._buf_index + 1) % self._buf_config.buf_size()
        # The buffer has been completely filled once the write index wraps
        # back to the beginning. From this point onward, the oldest frames
        # will be overwritten by newer ones.
        if self._buf_index == 0:
            self._ring_buf_fil_count += 1
            print(f"After ring buffer filled {self._ring_buf_fil_count}")

    # Returns the buffered frames in chronological order.
    def get_ordered_buf_frames(self):
        frames = []
        # Start from the oldest frame in the circular buffer.
        # _buf_index always points to the next position that will be overwritten.
        for i in range(self._buf_config.buf_size()):
            # Wrap around to the beginning of the buffer when the end is reached.
            index = (self._buf_index + i) % self._buf_config.buf_size()
            frame = self._buffer[index]
            # Ignore unused slots until the buffer has been filled for the first time.
            if frame is not None:
                frames.append(frame)
        return frames

    # Thermal frame differencing.
    def _detect_motion_lepton(self):
        img = self.csi1.snapshot()
        self._frame_count += 1
        if self._frame_count > self._bg_update_frames:
            self._frame_count = 0
            img.blend(self._extra_fb, alpha=(255 - self._bg_update_blend))
            self._extra_fb.draw_image(img)
        img.difference(self._extra_fb)
        hist = img.get_histogram()
        diff = hist.get_percentile(0.99).l_value - hist.get_percentile(0.90).l_value
        return diff > self._trigger_threshold

    async def detect_motion_async_lepton(self):
        img = await self._snapshot_async(self.csi1)
        if img is not None:
            self._frame_count += 1
            if self._frame_count > self._bg_update_frames:
                self._frame_count = 0
                img.blend(self._extra_fb, alpha=(255 - self._bg_update_blend))
                self._extra_fb.draw_image(img)
            img.difference(self._extra_fb)
            hist = img.get_histogram()
            diff = hist.get_percentile(0.99).l_value - hist.get_percentile(0.90).l_value
            return diff > self._trigger_threshold
        return False

    async def _snapshot_async(self, camera):
        while True:
            img = camera.snapshot(blocking=False)
            if img is not None:
                return img
            await asyncio.sleep_ms(0)

    # Clears the circular frame buffer after recording.
    def clear_frame_buffer(self):
        for i in range(self._buf_config.buf_size()):
            self._buffer[i] = None
        self._buf_index = 0
        self._last_frame_time = time.ticks_ms()