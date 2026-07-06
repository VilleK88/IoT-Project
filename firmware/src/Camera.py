from src.MotionConfig import MotionConfig
from src.BufferConfig import BufferConfig
import mjpeg
import csi
import machine
import time
import image
import gc


class Camera:
    def __init__(self, storage_config, file_manager):
        self.print_memory_status("Before CSI init")

        # External dependencies
        self._storage_config = storage_config
        self._file_manager = file_manager

        # Thermal detection settings
        self._threshold_list = [(200, 255)]
        self._min_temp_in_celsius = 20.0
        self._max_temp_in_celsius = 40.0
        self._therm_detect_counter = 0
        self._last_hot_img = None

        # Hardware indicators
        self._led = machine.LED("LED_RED") # Status LED is used to indicate active recording

        # Motion detection settings
        self._mot_conf = MotionConfig()
        self._triggered = False
        self._frame_count = 0
        self._last_motion_check_time = time.ticks_ms()

        # Buffer settings
        self._buf_config = BufferConfig()
        self._buffer = [None] * self._buf_config.buf_size()
        self._buf_index = 0
        self._last_frame_time = 0
        self._buf_start_time = time.ticks_ms()
        self._frame_interval_ms = self._buf_config.frame_interval_ms()

        # Initialize the OpenMV N6 PAG7936 CSI camera
        self.csi0 = csi.CSI()
        self.csi0.reset()
        self.csi0.pixformat(csi.RGB565)
        self.csi0.framesize(csi.VGA) # 640x480
        self._current_frame = self.csi0.snapshot(time=2000)
        self.csi0.auto_whitebal(False)

        # Motion background buffer and bg
        self._extra_fb = image.Image(self._mot_conf.motion_width(), self._mot_conf.motion_height(), csi.GRAYSCALE)
        self._ring_buf_fil_count = 0
        print("About to save background image...")
        self._extra_fb.draw_image(self.create_motion_frame(self.csi0.snapshot()))
        print("Saved background image - Now frame differencing!")

        # Initialize the OpenMV N6 Lepton CSI camera interface
        """self.csi1 = csi.CSI(cid=csi.LEPTON)
        self.csi1.reset()  # Reset and initialize the sensor
        self.csi1.pixformat(csi.GRAYSCALE)  # Set pixel format to RGB565 (or GRAYSCALE)
        self.csi1.framesize(csi.QQVGA)  # Set frame size to QQVGA (160×120)
        self.csi1.snapshot(time=5000)
        # Enable measurement mode
        self.csi1.ioctl(csi.IOCTL_LEPTON_SET_MODE, True, True)
        self.csi1.ioctl(csi.IOCTL_LEPTON_SET_RANGE, self._min_temp_in_celsius, self._max_temp_in_celsius)
        self.print_memory_status("After Lepton CSI config")"""

        self._therm_frame_max_time_ms = 200
        self._last_therm_frame_time = time.ticks_ms()

    def detect_motion(self):
        img = self.create_motion_frame(self._current_frame)
        self._frame_count += 1

        if self._frame_count > self._mot_conf.bg_upd_frames():
            self._frame_count = 0
            # Blend in new frame
            img.blend(self._extra_fb, alpha=(255 - self._mot_conf.bg_upd_blend()))
            self._extra_fb.draw_image(img)

        # Replace the image with the "abs(NEW_OLD)" frame difference
        img.difference(self._extra_fb)

        hist = img.get_histogram()
        diff = hist.get_percentile(0.99).l_value - hist.get_percentile(0.90).l_value

        # Motion is detected when the difference exceeds the configured threshold
        self._triggered = diff > self._mot_conf.trig_thresh()

        return self._triggered

    def should_check_motion(self):
        now = time.ticks_ms()
        if time.ticks_diff(now, self._last_motion_check_time) >= self._mot_conf.chk_mot_ms():
            self._last_motion_check_time = now
            return True
        return False

    def take_picture(self):
        self.csi0.auto_whitebal(True)
        img = self.csi0.snapshot()

        # Build a unique filename using the configured folder, prefix and suffix
        filename = self._file_manager.build_filename(
            self._storage_config.img_dir(),
            self._storage_config.img_prefix(),
            self._storage_config.img_suffix(),
            self._file_manager.get_img_count()
        )
        self._file_manager.increase_img_count()
        img.save(filename)
        self.csi0.auto_whitebal(False)

    def record_video(self):
        print("start recording")
        filename, video = self.create_motion_video()
        self.start_recording_state()

        # Motion is not checked every frame during recording. This reduces CPU load and improves stability.
        last_motion_check = time.ticks_ms()
        try:
            while True:
                img = self.csi0.snapshot()
                video.write(img)
                now = time.ticks_ms()

                # Periodically check whether motion is still present
                if time.ticks_diff(now, last_motion_check) >= self._mot_conf.rec_chk_int_ms():
                    last_motion_check = now
                    diff = self.get_motion_diff(img)

                    if diff <= self._mot_conf.trig_thresh():
                        break
                    else:
                        print("Motion detected while recording")
        finally:
            # Always close the MJPEG file even if recording exits unexpectedly
            video.close()
            self.stop_recording_state()

        print("record_video done")
        # Short cooldown helps prevent immediate repeated recordings
        time.sleep_ms(self._mot_conf.post_rec_cd_ms())
        self._frame_count = 0

    def record_video_with_prebuffer(self):
        self.print_memory_status("Before recording with prebuffer")
        filename, video = self.create_motion_video()
        self.start_recording_state()

        saved_frames = 0
        try:
            saved_frames = self.write_prebuffer_with_catchup(video) # Include frames in the frame buffer to mjpeg
            self.csi0.framesize(csi.HD) # Increase frame size to 1280x720
            last_live_frame_time = time.ticks_ms()
            last_motion_check = time.ticks_ms()

            while True:
                now = time.ticks_ms()

                if time.ticks_diff(now, last_live_frame_time) >= self._frame_interval_ms:
                    last_live_frame_time = now

                    img = self.csi0.snapshot()
                    video.write(img)
                    saved_frames += 1

                    # Periodically check whether motion is still present
                    if time.ticks_diff(now, last_motion_check) >= self._mot_conf.rec_chk_int_ms():
                        last_motion_check = now
                        diff = self.get_motion_diff(img)

                        if diff <= self._mot_conf.trig_thresh():
                            break
                        else:
                            print("Motion detected while recording")
        finally:
            video.close() # Always close the MJPEG file even if recording exits unexpectedly
            self.stop_recording_state()

        duration_ms = saved_frames * self._frame_interval_ms
        self._file_manager.patch_mjpeg_timing(filename, saved_frames, duration_ms)

        print("record_video_with_prebuffer done")
        print("Saved frames:", saved_frames)
        print("Duration ms:", duration_ms)

        self.csi0.framesize(csi.VGA) # Decrease frame size back to 640x480
        time.sleep_ms(self._mot_conf.post_rec_cd_ms()) # Short cooldown helps prevent immediate repeated recordings
        self._frame_count = 0
        self.print_memory_status("After recording with prebuffer")

    def create_motion_video(self):
        filename = self._file_manager.build_filename(
            self._storage_config.vid_dir(),
            self._storage_config.vid_prefix(),
            self._storage_config.vid_suffix(),
            self._file_manager.get_video_count()
        )
        self._file_manager.increase_video_count()
        print("Recording:", filename)
        return filename, mjpeg.Mjpeg(filename)

    def start_recording_state(self):
        self._led.on()
        self.csi0.auto_whitebal(True)

    def stop_recording_state(self):
        self._led.off()
        self.csi0.auto_whitebal(False)

    def write_prebuffer_with_catchup(self, video):
        last_live_frame_time = time.ticks_ms()
        saved_frames = 0
        prebuf_frames = self.get_ordered_buf_frames()
        catchup_frames = []

        # Write pre-buffer while also sampling new frames during the blocking write
        for frame in prebuf_frames:
            video.write(frame)
            saved_frames += 1

            now = time.ticks_ms()

            if time.ticks_diff(now, last_live_frame_time) >= self._frame_interval_ms:
                self._current_frame = self.csi0.snapshot()
                catchup_frames.append(self._current_frame.copy())
                last_live_frame_time = now

        # Write frames captured while the pre-buffer was being written
        for frame in catchup_frames:
            video.write(frame)
            saved_frames += 1

        return saved_frames

    def get_motion_diff(self, frame):
        img = self.create_motion_frame(frame)
        img.difference(self._extra_fb) # Compare the current frame against the bg img
        hist = img.get_histogram() # Calculate the amount of motion from the difference img
        diff = hist.get_percentile(0.99).l_value - hist.get_percentile(0.90).l_value
        return diff

    def update_frame_buffer(self):
        now = time.ticks_ms()

        if time.ticks_diff(now, self._last_frame_time) >= self._buf_config.frame_interval_ms():
            self._current_frame = self.csi0.snapshot()
            # Store a copy of the current frame in the circular buffer.
            # PAG7936 csi.VGA RGB565: ~500 KiB (0.488 MiB) RAM per buffered frame.
            self.save_frame(self._current_frame.copy())
            self._last_frame_time = now

    def save_frame(self, frame):
        self._buffer[self._buf_index] = frame
        self._buf_index = (self._buf_index + 1) % self._buf_config.buf_size()

        if self._buf_index == 0:
            self.cleanup_memory()
            self._ring_buf_fil_count += 1
            print("After ring buffer filled", self._ring_buf_fil_count)
            print("Free:", gc.mem_free())
            print("Allocated:", gc.mem_alloc())

    def save_buf_as_mjpeg(self):
        print("saving buffer")
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
            saved_frames = self.write_buf_to_video(video)
        finally:
            # Finish and close the MJPEG file
            video.close()

        duration_ms = saved_frames * self._buf_config.frame_interval_ms()
        self._file_manager.patch_mjpeg_timing(filename, saved_frames, duration_ms)
        print("buffer saved, frames:", saved_frames)

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

    def get_ordered_buf_frames(self):
        frames = []

        for i in range(self._buf_config.buf_size()):
            index = (self._buf_index + i) % self._buf_config.buf_size()
            frame = self._buffer[index]

            if frame is not None:
                frames.append(frame)

        return frames

    def create_motion_frame(self, frame):
        img = frame.copy(
            x_scale=self._mot_conf.motion_width() / frame.width(),
            y_scale=self._mot_conf.motion_height() / frame.height()
        )
        img.to_grayscale()
        return img

    def map_g_to_temp(self, g):
        return ((g * (self._max_temp_in_celsius - self._min_temp_in_celsius)) / 255.0) + self._min_temp_in_celsius

    """def thermal_camera(self):
        now = time.ticks_ms()

        if time.ticks_diff(now, self._last_therm_frame_time) >= self._therm_frame_max_time_ms:
            self._last_therm_frame_time = now
            #self.print_memory_status("Before taking picture")
            img = self.csi1.snapshot()
            #self.print_memory_status("After taking picture")
            for blob in img.find_blobs(
                self._threshold_list, pixels_threshold=200, area_threshold=200, merge=True
            ):
                stats = img.get_statistics(threshold=self._threshold_list, roi=blob.rect)
                img.draw_detection(blob, label="%.2f C" % self.map_g_to_temp(stats.mean))"""

    def init_camera(self):
        # PAG7936 camera setup
        """self.csi0 = csi.CSI()
        self.csi0.reset() # Reset and initialize the sensor
        self.csi0.pixformat(csi.RGB565) # Set pixel format to RGB565 (or GRAYSCALE)
        self.csi0.framesize(csi.VGA) # PAG7936 csi.VGA = 640x400
        img = self.csi0.snapshot(time=2000)
        self.csi0.auto_whitebal(False)
        self.print_memory_status("After PAG7936 CSI config and first VGA snapshot")
        return img"""

    def init_thermal_camera(self):
        # Lepton thermal camera setup
        """self.csi1 = csi.CSI(cid=csi.LEPTON)
        self.csi1.reset()  # Reset and initialize the sensor
        self.csi1.pixformat(csi.GRAYSCALE)  # Set pixel format to RGB565 (or GRAYSCALE)
        self.csi1.framesize(csi.QQVGA)  # Set frame size to QQVGA (160×120)

        self.csi1.snapshot(time=5000)

        # Enable measurement mode
        self.csi1.ioctl(csi.IOCTL_LEPTON_SET_MODE, True, True)
        self.csi1.ioctl(csi.IOCTL_LEPTON_SET_RANGE, self._min_temp_in_celsius, self._max_temp_in_celsius)

        self.print_memory_status("After Lepton CSI config")"""

    """def deinit_thermal_camera(self):
        if self.csi1 is not None:
            self.csi1.sleep(True)
            self.csi1 = None
            self.cleanup_memory()"""

    def cleanup_memory(self):
        gc.collect()

    def print_memory_status(self, label):
        self.cleanup_memory()
        print(label)
        print("Free:", gc.mem_free())
        print("Allocated:", gc.mem_alloc())
