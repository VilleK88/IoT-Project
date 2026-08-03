from src.MotionConfig import MotionConfig
from src.BufferConfig import BufferConfig
from src.UploadConfig import UploadConfig
from src.Tools import Tools
import mjpeg
import image
import csi
import machine
import time

class Camera:
    # Initializes the camera system and all runtime resources.
    def __init__(self, storage_config, file_manager, network_manager):
        self._tools = Tools()
        self._tools.print_memory_status("Before CSI init")

        self._network_manager = network_manager

        # External dependencies
        self._storage_config = storage_config
        self._file_manager = file_manager

        self._upload_config = UploadConfig()

        # Hardware indicators
        self._led = machine.LED("LED_RED") # Status LED is used to indicate active recording

        # Motion detection settings
        self._mot_conf = MotionConfig()
        self._last_motion_check_time = time.ticks_ms()

        # RGB movement detection settings
        self._max_recording_time_ms = 2 * 60 * 1000  # Maximum recording duration 2 minutes.

        # Buffer settings
        self._buf_config = BufferConfig()
        self._buffer = [None] * self._buf_config.buf_size()
        self._buf_index = 0
        self._last_frame_time = 0
        self._frame_interval_ms = self._buf_config.frame_interval_ms()
        self._ring_buf_fil_count = 0

        # Initialize the OpenMV N6 PAG7936 CSI camera
        self.csi0 = csi.CSI()  # Create a new CSI camera object.
        self.csi0.reset()  # Initialize and reset the connected camera sensor.
        self.csi0.pixformat(csi.RGB565)
        self.csi0.framesize(csi.VGA) # 640x480
        self._current_frame = self.csi0.snapshot(time=2000)  # Let new settings take effect.
        self.csi0.auto_whitebal(True)  # Enable automatic white balance for improved image quality.

        # Thermal detection settings
        # Minimum grayscale value considered warm enough to belong to a thermal target.
        self._min_temp_in_celsius = 20.0  # Minimum temperature represented by grayscale value 0.
        self._max_temp_in_celsius = 40.0  # Maximum temperature represented by grayscale value 255.

        # Initialize the OpenMV N6 Lepton CSI camera interface
        self.csi1 = csi.CSI(cid=csi.LEPTON)
        self.csi1.reset(hard=False)  # Reset and initialize the sensor
        self.csi1.pixformat(csi.GRAYSCALE)  # Set pixel format to RGB565 (or GRAYSCALE)
        self.csi1.framesize(csi.QQVGA)  # Set frame size to QQVGA (160x120)
        # Enable measurement mode
        self.csi1.ioctl(csi.IOCTL_LEPTON_SET_MODE, True, True)
        self.csi1.ioctl(csi.IOCTL_LEPTON_SET_RANGE, self._min_temp_in_celsius, self._max_temp_in_celsius)

        self.csi1.snapshot(time=5000) # Let new settings take effect.
        self._extra_fb = image.Image(self.csi1.width(), self.csi1.height(), self.csi1.pixformat())
        print("About to save background image...")
        self._extra_fb.draw_image(self.csi1.snapshot())
        print("Saved background image - Now frame differencing!")
        self._triggered = False
        self._frame_count = 0
        self._trigger_threshold = 5
        self._bg_update_frames = 5
        self._bg_update_blend = 128
        self._tools.print_memory_status("After Lepton CSI config")

        # Reusable 1280x800 RGB565 frame used for scaling pre-buffer frames.
        # Allocate it before the circular buffer fragments the heap.
        self._scaled_frame = image.Image(1280, 800, csi.RGB565)



    # Returns True when it is time to perform the next motion check.
    def should_check_motion(self):
        now = time.ticks_ms()
        if time.ticks_diff(now, self._last_motion_check_time) >= self._mot_conf.chk_mot_ms():
            self._last_motion_check_time = now
            return True
        return False

    # Captures and saves a single RGB image.
    # Currently not used by the recording pipeline, but kept for
    # future features such as event snapshots or debugging.
    def take_picture(self):
        # Capture a full-resolution RGB image.
        img = self.csi0.snapshot()
        # Build a unique filename using the configured folder, prefix,
        # suffix and the next available image number.
        filename = self._file_manager.build_filename(
            self._storage_config.img_dir(),
            self._storage_config.img_prefix(),
            self._storage_config.img_suffix(),
            self._file_manager.get_img_count()
        )
        # Reserve the next image number for future captures.
        self._file_manager.increase_img_count()
        # Save the image to the SD card.
        img.save(filename)

    # Records an MJPEG video beginning with the buffered frames
    # followed by live RGB frames.
    def record_video(self):
        self._tools.print_memory_status("Before recording with prebuffer")
        # Create a new MJPEG file and prepare the camera for recording.
        filename, video = self.create_motion_video()
        saved_frames = 0
        try:
            # Save the buffered thermal frames before switching to the RGB camera.
            saved_frames = self.write_prebuffer_with_catchup(video)
            self.start_recording_state()
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
                    print("Captured frame:", img.width(), img.height())
                    self._current_frame = img
                    video.write(img)  # Append the frame to the MJPEG video.
                    saved_frames += 1
                    # Check for movement at the configured interval.
                    if time.ticks_diff(now, last_motion_check) >= self._mot_conf.chk_mot_ms():
                        last_motion_check = now
                        # Reset the no-motion timer whenever movement is detected.
                        if self.detect_motion():
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
            print("Saved frames:", saved_frames)
            print("Duration ms:", duration_ms)
            self._tools.print_memory_status("record_video_with_prebuffer done")
            # Upload the recording immediately if configured.
            if self._upload_config.current_setting() == "Instantly":
                self._network_manager.upload_mjpeg(filename)
                self._tools.print_memory_status("upload_mjpeg done")
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
        # Create and return the MJPEG video object.
        return filename, mjpeg.Mjpeg(filename, width=1280, height=800)

    # Enables the hardware and camera settings required for recording.
    def start_recording_state(self):
        self.csi0.framesize(csi.HD)  # 1280x800
        print("CSI resolution:", self.csi0.width(), self.csi0.height())
        self._led.on()  # Turn on the recording status LED.

    # Restores the camera state after recording has finished.
    def stop_recording_state(self):
        # Remove any buffered frames so the next recording starts with
        self.clear_frame_buffer()  # a fresh circular buffer.
        self.csi0.framesize(csi.VGA)  # 640x480

    # Writes the buffered frames to the MJPEG file.
    # New thermal frames are sampled while writing to avoid a capture gap.
    def write_prebuffer_with_catchup(self, video):
        last_live_frame_time = time.ticks_ms()
        saved_frames = 0
        # Retrieve the buffered frames in chronological order.
        prebuf_frames = self.get_ordered_buf_frames()
        # Stores frames captured while the pre-buffer is being written.
        # These frames are appended afterwards to reduce the recording gap.
        catchup_frames = []
        # Write the buffered frames to the MJPEG file.
        for frame in prebuf_frames:
            scaled_frame = self.scale_frame(frame)
            video.write(scaled_frame)
            saved_frames += 1
            # Periodically capture a new thermal frame while writing to
            # compensate for the time spent saving the pre-buffer.
            now = time.ticks_ms()
            if time.ticks_diff(now, last_live_frame_time) >= self._frame_interval_ms:
                self._current_frame = self.csi0.snapshot()
                catchup_frames.append(self._current_frame.copy())
                last_live_frame_time = now
        # Append the frames captured during the pre-buffer write so the
        # transition from buffered video to live recording is as seamless as possible.
        for frame in catchup_frames:
            scaled_frame = self.scale_frame(frame)
            video.write(scaled_frame)
            saved_frames += 1
        return saved_frames

    def scale_frame(self, frame):
        self._scaled_frame.draw_image(frame, x_scale=2.0, y_scale=2.0)
        print("Scaled:", self._scaled_frame.width(), self._scaled_frame.height())
        return self._scaled_frame

    # Periodically captures thermal frames into the circular RAM buffer.
    def update_frame_buffer(self):
        now = time.ticks_ms()
        # Capture a new frame only when the configured buffer interval has elapsed.
        # This keeps the buffer at a fixed frame rate regardless of the main loop speed.
        if time.ticks_diff(now, self._last_frame_time) >= self._buf_config.frame_interval_ms():
            # Capture the latest frame from the Lepton thermal camera.
            self._current_frame = self.csi0.snapshot()
            # Store a copy of the current frame in the circular buffer.
            # A copy is required because snapshot() reuses the same image buffer.
            self.save_frame(self._current_frame.copy())
            self._last_frame_time = now

    # Stores a frame in the circular buffer and advances the write index.
    def save_frame(self, frame):
        # Store the newest frame at the current write position.
        self._buffer[self._buf_index] = frame
        # Advance the write index and wrap back to the beginning when the
        # end of the circular buffer is reached.
        self._buf_index = (self._buf_index + 1) % self._buf_config.buf_size()
        # The buffer has been completely filled once the write index wraps
        # back to the beginning. From this point onward, the oldest frames
        # will be overwritten by newer ones.
        if self._buf_index == 0:
            # Run garbage collection after one complete buffer cycle to help
            # keep memory usage stable during long-running operation.
            self._tools.cleanup_memory()
            self._ring_buf_fil_count += 1
            self._tools.print_memory_status(f"After ring buffer filled {self._ring_buf_fil_count}")

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
    def detect_motion(self):
        img = self.csi1.snapshot()
        self._frame_count += 1
        if self._frame_count > self._bg_update_frames:
            self._frame_count = 0
            img.blend(self._extra_fb, alpha=(255 - self._bg_update_blend))
            self._extra_fb.draw_image(img)
        img.difference(self._extra_fb)
        hist = img.get_histogram()
        diff = hist.get_percentile(0.99).l_value - hist.get_percentile(0.90).l_value
        self._triggered = diff > self._trigger_threshold
        return self._triggered

    # Clears the circular frame buffer after recording.
    def clear_frame_buffer(self):
        for i in range(self._buf_config.buf_size()):
            self._buffer[i] = None
        self._buf_index = 0
        self._last_frame_time = time.ticks_ms()