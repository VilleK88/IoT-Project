from src.MotionConfig import MotionConfig
from src.StorageConfig import StorageConfig
from src.BufferConfig import BufferConfig
import mjpeg
import csi
import machine
import os
import time
import image
import gc


class Camera:
    def __init__(self):
        self.csi0 = csi.CSI() # Initialize the OpenMV N6 CSI camera interface
        self.csi0.reset() # Reset and initialize the sensor
        self.csi0.pixformat(csi.RGB565) # Set pixel format to RGB565 (or GRAYSCALE)
        self.csi0.framesize(csi.QVGA) # Set frame size to QVGA (320x240)
        self.csi0.snapshot(time=2000) # Wait for settings take effect
        self.csi0.auto_whitebal(False) # Turn off white balance

        self._led = machine.LED("LED_RED") # Status LED is used to indicate active recording

        self._storage_config = StorageConfig() # Load storage settings and ensure output folders exist

        self.create_directory(self._storage_config.vid_dir())
        self.create_directory(self._storage_config.img_dir())
        self.create_directory(self._storage_config.temp_dir())
        self.create_directory(self._storage_config.pre_buf_dir())

        # Continue numbering from the highest existing file number
        self._vid_count = self.get_next_file_num(
            self._storage_config.vid_dir(),
            self._storage_config.vid_prefix(),
            self._storage_config.vid_suffix()
        )

        self._img_count = self.get_next_file_num(
            self._storage_config.img_dir(),
            self._storage_config.img_prefix(),
            self._storage_config.img_suffix()
        )

        self._pre_buf_count = self.get_next_file_num(
            self._storage_config.pre_buf_dir(),
            self._storage_config.vid_prefix(),
            self._storage_config.vid_suffix()
        )

        # Load motion detection thresholds and timing settings
        self._motion_config = MotionConfig()

        # Create a second frame buffer on the heap
        self._extra_fb = image.Image(self.csi0.width(), self.csi0.height(), self.csi0.pixformat())

        self.save_bg_img(2000)

        self._triggered = False
        self._frame_count = 0

        # Buffer settings
        self._buf_config = BufferConfig()
        self._buffer = [None] * self._buf_config.buf_size()
        self._buf_index = 0
        self._last_frame_time = 0
        self._buf_start_time = time.ticks_ms()

        self._last_motion_check_time = time.ticks_ms()

    def detect_motion(self, img):
        #self.csi0.auto_whitebal(False)
        #img = self.csi0.snapshot() # Take a picture and return the image

        self._frame_count += 1
        if self._frame_count > self._motion_config.bg_upd_frames():
            self._frame_count = 0
            # Blend in new frame
            img.blend(self._extra_fb, alpha=(255 - self._motion_config.bg_upd_blend()))
            self._extra_fb.draw_image(img)

        # Replace the image with the "abs(NEW_OLD)" frame difference
        img.difference(self._extra_fb)

        hist = img.get_histogram()
        diff = hist.get_percentile(0.99).l_value() - hist.get_percentile(0.90).l_value()

        # Motion is detected when the difference exceeds the configured threshold
        self._triggered = diff > self._motion_config.trig_thresh()

        return self._triggered

    def should_check_motion(self):
        now = time.ticks_ms()

        if time.ticks_diff(now, self._last_motion_check_time) < self._motion_config.chk_mot_ms():
            return False

        self._last_motion_check_time = now
        return True

    def take_picture(self):
        self.csi0.auto_whitebal(True)
        img = self.csi0.snapshot()

        # Build a unique filename using the configured folder, prefix and suffix
        filename = self.build_filename(
            self._storage_config.img_dir(),
            self._storage_config.img_prefix(),
            self._storage_config.img_suffix(),
            self._img_count
        )
        self._img_count += 1
        img.save(filename)
        self.csi0.auto_whitebal(False)

    def record_video(self):
        print("start recording")

        filename = self.build_filename(
            self._storage_config.vid_dir(),
            self._storage_config.vid_prefix(),
            self._storage_config.vid_suffix(),
            self._vid_count
        )
        self._vid_count += 1
        print("Recording:", filename)
        video = mjpeg.Mjpeg(filename)

        # LED stays on while the camera is recording
        self._led.on()

        self.csi0.auto_whitebal(True)
        # Motion is not checked every frame during recording.
        # This reduces CPU load and improves stability.
        last_motion_check = time.ticks_ms()

        try:
            while True:
                img = self.csi0.snapshot()
                # Write the normal camera frame before motion detection modifies it
                video.write(img)

                now = time.ticks_ms()

                # Periodically check whether motion is still present
                if time.ticks_diff(now, last_motion_check) >= self._motion_config.rec_chk_int_ms():
                    last_motion_check = now
                    diff = self.get_motion_diff(img.copy())

                    if diff <= self._motion_config.trig_thresh():
                        break
                    else:
                        print("Motion detected while recording")

        finally:
            # Always close the MJPEG file even if recording exits unexpectedly
            video.close()
            self._led.off()

        print("record_video done")
        self.csi0.auto_whitebal(False)
        # Short cooldown helps prevent immediate repeated recordings
        time.sleep_ms(self._motion_config.post_rec_cd_ms())

        self._frame_count = 0

    def get_next_file_num(self, directory, prefix, suffix):
        highest = self._storage_config.init_file_num()

        for filename in os.listdir(directory):
            if filename.startswith(prefix) and filename.endswith(suffix):
                number_part = filename[len(prefix):-len(suffix)]
                number = int(number_part)
                if number > highest:
                    highest = number

        return highest + 1

    def create_directory(self, path):
        try:
            os.mkdir(path)
            print("Directory created:", path)
        except OSError:
            print("Directory already exists:", path)

    def get_motion_diff(self, img):
        # Compare the current frame against the background image
        img.difference(self._extra_fb)

        # Calculate the amount of motion from the difference image
        hist = img.get_histogram()
        diff = hist.get_percentile(0.99).l_value() - hist.get_percentile(0.90).l_value()

        return diff

    def build_filename(self, directory, prefix, suffix, count):
        # Build a unique filename using the configured folder, prefix and suffix
        filename = "%s/%s%05d%s" % (
            directory,
            prefix,
            count,
            suffix
        )
        return filename

    def update_frame_buffer(self, frame):
        now = time.ticks_ms()

        interval_ms = 1000 // self._buf_config.buf_fps()

        if time.ticks_diff(now, self._last_frame_time) >= interval_ms:
            #frame = self.csi0.snapshot()
            self.save_frame(frame.copy())
            self._last_frame_time = now

    def save_frame(self, frame):
        self._buffer[self._buf_index] = frame
        self._buf_index = (self._buf_index + 1) % self._buf_config.buf_size()

    def save_buf_as_mjpeg(self):
        print("saving buffer")
        filename = self.build_filename(
            self._storage_config.pre_buf_dir(),
            self._storage_config.vid_prefix(),
            self._storage_config.vid_suffix(),
            self._pre_buf_count
        )
        self._pre_buf_count += 1

        duration_ms = self._buf_config.buf_size() * (1000 // self._buf_config.buf_fps())

        # Create a new MJPEG file on the SD card
        video = mjpeg.Mjpeg(filename)

        saved_frames = 0

        try:
            # Start from write_index because it points to the oldest frame
            for i in range(self._buf_config.buf_size()):
                index = (self._buf_index + i) % self._buf_config.buf_size()
                frame = self._buffer[index]

                # Skip empty slots if the buffer is not full yet
                if frame is not None:
                    video.write(frame)
                    #time.sleep_ms(1000 // self._buf_fps)
                    saved_frames += 1

        finally:
            # Finish and close the MJPEG file
            video.close()
            self.patch_mjpeg_timing(filename, saved_frames, duration_ms)

        print("buffer saved, frames:", saved_frames)

    def write_u32_le(self, file, value):
        file.write(bytes([
            value & 0xFF,
            value >> 8 & 0xFF,
            value >> 16 & 0xFF,
            value >> 24 & 0xFF
        ]))

    def patch_u32(self, file, offset, value):
        file.seek(offset)
        self.write_u32_le(file, value)

    def patch_mjpeg_timing(self, filename, frames, duration_ms):
        if frames <= 0 or duration_ms <= 0:
            return

        time_scale = 1000

        us_avg = (duration_ms * 1000) // frames
        rate = (1000000 * time_scale) // us_avg
        length = (frames * time_scale) // rate

        micros_offs = 8 * 4
        frames_offs = 12 * 4
        rate_0_offs = 19 * 4
        len_0_offs = 21 * 4
        rate_1_offs = 33 * 4
        len_1_offs = 35 * 4

        with open(filename, "r+b") as file:
            self.patch_u32(file, micros_offs, us_avg)
            self.patch_u32(file, frames_offs, frames)
            self.patch_u32(file, rate_0_offs, rate)
            self.patch_u32(file, len_0_offs, length)
            self.patch_u32(file, rate_1_offs, rate)
            self.patch_u32(file, len_1_offs, length)

        print("Patched MJPEG timing")
        print("Frames:", frames)
        print("Duration ms:", duration_ms)
        print("FPS:", (frames * 1000) // duration_ms)


    def save_bg_img(self, time_ms):
        print("About to save background image...")
        self.csi0.snapshot(time=time_ms) # Give the user time to get ready
        self._extra_fb.draw_image(self.csi0.snapshot())
        print("Saved background image - Now frame differencing!")

    def cleanup_memory(self):
        gc.collect()