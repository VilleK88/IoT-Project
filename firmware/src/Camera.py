from src.MotionConfig import MotionConfig
from src.BufferConfig import BufferConfig
from src.UploadConfig import UploadConfig
from src.Tools import Tools
import mjpeg
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
        self._previous_motion_frame = None  # Previous RGB frame used for movement comparison.
        self._motion_threshold = [(20, 255)]  # Minimum brightness change considered movement.
        self._motion_min_blob_pixels = 30  # 60 tested Minimum changed pixels required for a movement blob.
        self._motion_min_blob_area = 50  # 100 Minimum movement blob bounding box area.
        self._motion_max_blob_pixels = int(
            self._mot_conf.motion_width() * self._mot_conf.motion_height() * 0.50
        )  # Reject blobs covering more than 50% of the motion frame.
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
        self.csi0.framesize(csi.HD) # 1280x720
        self.csi0.snapshot(time=2000)  # Let new settings take effect.
        self.csi0.auto_whitebal(False)

        # Thermal detection settings
        # Minimum grayscale value considered warm enough to belong to a thermal target.
        self._threshold_list = [(100, 255)]  # 20 + (100 / 255 * 20) = 27.8 °C
        self._min_temp_in_celsius = 20.0  # Minimum temperature represented by grayscale value 0.
        self._max_temp_in_celsius = 40.0  # Maximum temperature represented by grayscale value 255.
        self._min_blob_pixels = 60  # Minimum number of hot pixels required for a blob to be considered a valid target.
        self._min_blob_area = 100  # Minimum blob bounding box area required for a valid target.
        self._max_blob_pixels = int(160 * 120 * 0.40)  # Reject blobs covering more than 40% of the thermal frame.

        # Initialize the OpenMV N6 Lepton CSI camera interface
        self.csi1 = csi.CSI(cid=csi.LEPTON)
        self.csi1.reset()  # Reset and initialize the sensor
        self.csi1.pixformat(csi.GRAYSCALE)  # Set pixel format to RGB565 (or GRAYSCALE)
        self.csi1.framesize(csi.QQVGA)  # Set frame size to QQVGA (160×120)
        self._current_frame = self.csi1.snapshot(time=5000) # Let new settings take effect.
        # Enable measurement mode
        self.csi1.ioctl(csi.IOCTL_LEPTON_SET_MODE, True, True)
        self.csi1.ioctl(csi.IOCTL_LEPTON_SET_RANGE, self._min_temp_in_celsius, self._max_temp_in_celsius)
        self._tools.print_memory_status("After Lepton CSI config")

    # Reinitializes the PAG7936 RGB camera after switching from the
    # Lepton thermal camera.
    def reinit_pag7936_camera(self):
        self.csi0.reset()
        self.csi0.pixformat(csi.RGB565)
        self.csi0.framesize(csi.HD)
        self.csi0.auto_whitebal(True)

    # Reinitializes the Lepton thermal camera after RGB recording ends.
    # The startup snapshot allows the thermal image to stabilize.
    def reinit_lepton_camera(self):
        self.csi1.reset()  # Reset and initialize the sensor
        self.csi1.pixformat(csi.GRAYSCALE)  # Set pixel format to RGB565 (or GRAYSCALE)
        self.csi1.framesize(csi.QQVGA)  # Set frame size to QQVGA (160×120)
        self._current_frame = self.csi1.snapshot(time=5000)
        # Enable measurement mode
        self.csi1.ioctl(csi.IOCTL_LEPTON_SET_MODE, True, True)
        self.csi1.ioctl(csi.IOCTL_LEPTON_SET_RANGE, self._min_temp_in_celsius, self._max_temp_in_celsius)

    # Shuts down the PAG7936 RGB camera before a blocking upload.
    def shutdown_pag7936_camera(self):
        print("Shutting down PAG7936 camera")
        self.csi0.shutdown(True)
        self._tools.cleanup_memory()
        self._tools.print_memory_status("After PAG7936 shutdown")

    # Detects meaningful movement by comparing consecutive RGB frames
    # captured during the same recording session.
    def detect_motion(self, frame):
        # Convert the full-resolution RGB frame into a smaller grayscale image
        # to reduce memory usage and speed up movement detection.
        current_frame = self.create_motion_frame(frame)

        # The first frame cannot be compared against anything yet, so store it
        # as the reference frame and keep the recording active.
        if self._previous_motion_frame is None:
            self._previous_motion_frame = current_frame
            return True

        # Create a difference image where unchanged pixels become dark and
        # pixels whose brightness changed become brighter.
        diff_img = current_frame.copy()
        diff_img.difference(self._previous_motion_frame)

        # Store the current frame as the reference for the next movement check.
        # This ensures that only consecutive RGB frames are compared.
        self._previous_motion_frame = current_frame

        # Convert the grayscale difference image into a binary movement mask.
        # Only pixels whose brightness changed by the configured amount remain white.
        diff_img.binary(self._motion_threshold)

        # Search the binary movement mask for connected regions of changed pixels.
        for blob in diff_img.find_blobs(
                self._threshold_list,
                pixels_threshold=self._motion_min_blob_pixels,
                area_threshold=self._motion_min_blob_area,
                merge=True
        ):
            frame.draw_detection(blob, color1=127)
            # Reject changes that cover an unrealistically large part of the frame,
            # because they are more likely caused by camera shake or lighting changes.
            if blob.pixels < self._motion_max_blob_pixels:
                print(
                    "Moving object detected:",
                    "pixels:", blob.pixels,
                    "area:", blob.area
                )
                return True
        # No sufficiently large and plausible movement region was found.
        print("No movement detected")
        return False

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
        # Enable automatic white balance to improve image quality.
        self.csi0.auto_whitebal(True)
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
        # Restore the default white balance setting used for motion detection.
        self.csi0.auto_whitebal(False)

    # Records an MJPEG video beginning with the buffered frames
    # followed by live RGB frames.
    def record_video(self):
        self._tools.print_memory_status("Before recording with prebuffer")
        # Create a new MJPEG file and prepare the camera for recording.
        filename, video = self.create_motion_video()
        self.start_recording_state()
        saved_frames = 0
        try:
            # Save the buffered thermal frames before switching to the RGB camera.
            saved_frames = self.write_prebuffer_with_catchup(video)
            # Switch from the Lepton thermal camera to the PAG7936 RGB camera.
            self.reinit_pag7936_camera()
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
                    video.write(img)  # Append the frame to the MJPEG video.
                    saved_frames += 1
                    # Check for movement at the configured interval.
                    if time.ticks_diff(now, last_motion_check) >= self._mot_conf.rec_chk_int_ms():
                        last_motion_check = now
                        # Reset the no-motion timer whenever movement is detected.
                        if self.detect_motion(img):
                            last_motion_time = now
                        # Stop recording after the configured period without movement.
                        elif time.ticks_diff(now, last_motion_time) >= self._mot_conf.motion_timeout_ms():
                            break
        finally:
            video.close() # Always close the MJPEG file, even if recording exits unexpectedly.
            self.stop_recording_state() # Restore the default camera state after recording.
            # Update the MJPEG timing so playback matches the original capture rate.
            duration_ms = saved_frames * self._frame_interval_ms
            self._file_manager.patch_mjpeg_timing(filename, saved_frames, duration_ms)
            self._file_manager.patch_mjpeg_index(filename)
            print("Saved frames:", saved_frames)
            print("Duration ms:", duration_ms)
            self._tools.print_memory_status("record_video_with_prebuffer done")
            # Upload the recording immediately if configured.
            if self._upload_config.current_setting() == "Instantly":
                self.shutdown_pag7936_camera()
                self._network_manager.upload_mjpeg(filename)
                self._tools.print_memory_status("upload_mjpeg done")
            # Return to thermal monitoring mode.
            self.reinit_lepton_camera()

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
        return filename, mjpeg.Mjpeg(filename)

    # Enables the hardware and camera settings required for recording.
    def start_recording_state(self):
        self._led.on()  # Turn on the recording status LED.
        self.csi0.auto_whitebal(True)  # Enable automatic white balance for improved image quality.

    # Restores the camera state after recording has finished.
    def stop_recording_state(self):
        # Remove any buffered frames so the next recording starts with
        self.clear_frame_buffer()  # a fresh circular buffer.
        self._previous_motion_frame = None
        self._led.off()  # Turn off the recording status LED.
        self.csi0.auto_whitebal(False)  # Restore the default white balance setting used outside recording.

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
            video.write(frame)
            saved_frames += 1
            # Periodically capture a new thermal frame while writing to
            # compensate for the time spent saving the pre-buffer.
            now = time.ticks_ms()
            if time.ticks_diff(now, last_live_frame_time) >= self._frame_interval_ms:
                self._current_frame = self.csi1.snapshot()
                catchup_frames.append(self._current_frame.copy())
                last_live_frame_time = now
        # Append the frames captured during the pre-buffer write so the
        # transition from buffered video to live recording is as seamless as possible.
        for frame in catchup_frames:
            video.write(frame)
            saved_frames += 1
        return saved_frames

    # Periodically captures thermal frames into the circular RAM buffer.
    def update_frame_buffer(self):
        now = time.ticks_ms()
        # Capture a new frame only when the configured buffer interval has elapsed.
        # This keeps the buffer at a fixed frame rate regardless of the main loop speed.
        if time.ticks_diff(now, self._last_frame_time) >= self._buf_config.frame_interval_ms():
            # Capture the latest frame from the Lepton thermal camera.
            self._current_frame = self.csi1.snapshot()
            self._current_frame.flush()
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

    # Saves the current circular buffer as an MJPEG video.
    def save_buf_as_mjpeg(self):
        print("saving buffer")
        # Build a unique filename for the buffered video.
        filename = self._file_manager.build_filename(
            self._storage_config.pre_buf_dir(),
            self._storage_config.vid_prefix(),
            self._storage_config.vid_suffix(),
            self._file_manager.get_pre_buf_count()
        )
        self._file_manager.increase_pre_buf_count()
        # Create a new MJPEG file on the SD card
        video = mjpeg.Mjpeg(filename)
        saved_frames = 0
        try:
            # Write all buffered frames to the MJPEG file.
            saved_frames = self.write_buf_to_video(video)
        finally:
            # Always close the MJPEG file, even if writing fails.
            video.close()
            # Restore the original recording duration by patching the
            # MJPEG timing information after all frames have been written.
            duration_ms = saved_frames * self._buf_config.frame_interval_ms()
            self._file_manager.patch_mjpeg_timing(filename, saved_frames, duration_ms)
            print("buffer saved, frames:", saved_frames)

    # Writes the contents of the circular buffer to an MJPEG file.
    def write_buf_to_video(self, video):
        saved_frames = 0
        # Start from write_index because it points to the oldest frame
        for i in range(self._buf_config.buf_size()):
            index = (self._buf_index + i) % self._buf_config.buf_size()
            frame = self._buffer[index]
            # Skip empty slots if the buffer is not full yet
            if frame is not None:
                video.write(frame)
                saved_frames += 1
        return saved_frames

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

    # Creates a smaller grayscale frame for motion detection.
    def create_motion_frame(self, frame):
        img = frame.copy(
            x_scale=self._mot_conf.motion_width() / frame.width(),
            y_scale=self._mot_conf.motion_height() / frame.height()
        )
        img.to_grayscale()
        return img

    # Converts an 8-bit grayscale value to an estimated temperature.
    def map_g_to_temp(self, g):
        return ((g * (self._max_temp_in_celsius - self._min_temp_in_celsius)) / 255.0) + self._min_temp_in_celsius

    # Detects moving warm objects using the Lepton thermal camera.
    def thermal_detection(self):
        img = self._current_frame
        # Continue only if the frame contains a region significantly warmer
        # than the average scene temperature.
        if self.warm_region(img):
            # Search for warm regions that match the configured blob limits.
            if self.detect_warm_blobs(img):
                return True
        return False

    # Returns True when the frame contains a sufficiently warm region.
    def warm_region(self, img):
        # Estimate the hottest and average temperatures in the frame.
        stats = img.get_statistics()
        max_temp = self.map_g_to_temp(stats.max)
        mean_temp = self.map_g_to_temp(stats.mean)
        # Require the hottest point to be significantly warmer than the
        # average scene temperature.
        if max_temp - mean_temp > 6.0:
            return True
        return False

    # Searches for warm blobs that could represent an animal.
    def detect_warm_blobs(self, img):
        for blob in img.find_blobs(
            self._threshold_list,
                pixels_threshold=self._min_blob_pixels,
                area_threshold=self._min_blob_area,
                merge=True
        ):
            # Draw the detected warm blob for debugging.
            img.draw_detection(blob, color1=127)
            img.flush()
            # Ignore blobs that are unrealistically large, such as a warm wall
            # or another large heated background region.
            if blob.pixels < self._max_blob_pixels:
                print("Target found")
                return True
        img.flush()
        return False

    # Clears the circular frame buffer after recording.
    def clear_frame_buffer(self):
        for i in range(self._buf_config.buf_size()):
            self._buffer[i] = None
        self._buf_index = 0
        self._last_frame_time = time.ticks_ms()