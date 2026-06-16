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

        # Load motion detection thresholds and timing settings
        self._motion_config = MotionConfig()

        # Create a second frame buffer on the heap
        self._extra_fb = image.Image(self.csi0.width(), self.csi0.height(), self.csi0.pixformat())

        self.save_bg_img(2000)

        self._triggered = False
        self._frame_count = 0

        # Butter settings
        self._buffer_config = BufferConfig()
        self._frame_buffer = [None] * self._buffer_config.buffer_size()
        self._buffer_index = 0
        self._last_buffer_frame_time = time.ticks_ms()

    def detect_motion(self):
        img = self.csi0.snapshot() # Take a picture and return the image

        self._frame_count += 1
        if self._frame_count > self._motion_config.bg_update_frames():
            self._frame_count = 0
            # Blend in new frame
            img.blend(self._extra_fb, alpha=(255 - self._motion_config.bg_update_blend()))
            self._extra_fb.draw_image(img)

        # Replace the image with the "abs(NEW_OLD)" frame difference
        img.difference(self._extra_fb)

        hist = img.get_histogram()
        diff = hist.get_percentile(0.99).l_value() - hist.get_percentile(0.90).l_value()

        # Motion is detected when the difference exceeds the configured threshold
        self._triggered = diff > self._motion_config.trigger_threshold()

        return self._triggered

    def take_picture(self):
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
                if time.ticks_diff(now, last_motion_check) >= self._motion_config.record_check_interval_ms():
                    last_motion_check = now
                    diff = self.get_motion_diff(img)

                    if diff <= self._motion_config.trigger_threshold():
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
        time.sleep_ms(self._motion_config.post_record_cooldown_ms())

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

    def write_to_memory_stream(self):
        print("memory before writing to memory stream:", gc.mem_free())
        N_FRAMES = 200
        self.csi0.auto_whitebal(True)
        self.csi0.window((120, 120))
        self.csi0.snapshot(time=2000)

        # Write to memory stream
        stream = image.ImageIO((120, 120, csi.RGB565), N_FRAMES)
        print("Start writing to memory stream")
        for i in range(0, N_FRAMES):
            stream.write(self.csi0.snapshot())

        print("End writing to memory stream")

        print("Start reading from memory stream")
        stream.seek(0)
        for i in range(0, N_FRAMES):
            img = stream.read(copy_to_fb=True, pause=True)
        print("Stop reading from memory stream")
        print("memory after writing to memory stream:", gc.mem_free())
        self.cleanup_memory()
        print("memory after cleanup memory:", gc.mem_free())

        self.csi0.auto_whitebal(False)
        self.save_bg_img(1000)

    def save_bg_img(self, time_ms):
        print("About to save background image...")
        self.csi0.snapshot(time=time_ms) # Give the user time to get ready
        self._extra_fb.draw_image(self.csi0.snapshot())
        print("Saved background image - Now frame differencing!")

    def cleanup_memory(self):
        gc.collect()