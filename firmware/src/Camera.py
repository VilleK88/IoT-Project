from src.MotionConfig import MotionConfig
from src.StorageConfig import StorageConfig
import mjpeg
import csi
import machine
import os
import time


class Camera:
    def __init__(self):
        self.csi0 = csi.CSI()
        self.csi0.reset()
        self.csi0.pixformat(csi.RGB565)
        self.csi0.framesize(csi.QVGA)
        print("camera created")

        self._led = machine.LED("LED_RED")
        print("Created a handle to the OpenMV red status LED")

        self._storage_config = StorageConfig()

        self.create_directory(self._storage_config.video_folder())
        self.create_directory(self._storage_config.image_folder())

        self._video_count = self.get_next_file_num(
            self._storage_config.video_folder(),
            self._storage_config.video_prefix(),
            self._storage_config.video_suffix()
        )

        self._image_count = self.get_next_file_num(
            self._storage_config.image_folder(),
            self._storage_config.image_prefix(),
            self._storage_config.image_suffix()
        )

        self._motion_config = MotionConfig()

        self._extra_fb = self.csi0.snapshot().copy()
        print("About to save background image...")

        # Allow the camera image to stabilize before capturing
        # the initial background frame
        time.sleep_ms(2000)
        self.stabilize_camera(100)

        print("Saved background image")
        self._triggered = False
        self._frame_count = 0

    def detect_motion(self):
        # Capture the current frame
        img = self.csi0.snapshot()

        self._frame_count += 1

        # Periodically update the background image to adapt
        # to slow lighting changes
        if self._frame_count > self._motion_config.bg_update_frames():
            self._frame_count = 0

            bg_update = img.copy()
            bg_update.blend(self._extra_fb, alpha=(255 - self._motion_config.bg_update_blend()))

            self._extra_fb.replace(bg_update)

        diff = self.get_motion_diff(img)

        # Motion is detected when the difference exceeds
        # the configured threshold
        self._triggered = diff > self._motion_config.trigger_threshold()

        return self._triggered

    def take_picture(self):
        img = self.csi0.snapshot()

        filename = "%s/%s%05d%s" % (
            self._storage_config.image_folder(),
            self._storage_config.image_prefix(),
            self._image_count,
            self._storage_config.image_suffix()
        )

        self._image_count += 1
        img.save(filename)

    def record_video(self):
        print("start recording")

        filename = "%s/%s%05d%s" % (
            self._storage_config.video_folder(),
            self._storage_config.video_prefix(),
            self._video_count,
            self._storage_config.video_suffix()
        )

        self._video_count += 1
        print("Recording:", filename)
        video = mjpeg.Mjpeg(filename)
        self._led.on()

        last_motion_check = time.ticks_ms()

        try:
            while True:
                img = self.csi0.snapshot()
                video.write(img)
                now = time.ticks_ms()
                if time.ticks_diff(now, last_motion_check) >= self._motion_config.record_check_interval_ms():
                    last_motion_check = now
                    diff = self.get_motion_diff(img)
                    if diff <= self._motion_config.trigger_threshold():
                        break
        finally:
            video.close()
            self._led.off()

        print("record_video done")
        time.sleep_ms(self._motion_config.post_record_cooldown_ms())

        self._frame_count = 0

    def debug_record_video(self, duration_seconds=10):
        print("debug recording start")
        self._led.on()

        start_time = time.ticks_ms()

        try:
            while time.ticks_diff(time.ticks_ms(), start_time) < duration_seconds * 1000:
                self.csi0.snapshot()

        finally:
            self._led.off()
        print("debug recording done")

    def get_next_file_num(self, directory, prefix, suffix):
        highest = -1

        for filename in os.listdir(directory):
            if filename.startswith(prefix) and filename.endswith(suffix):
                number_part = filename[len(prefix):-len(suffix)]
                number = int(number_part)
                if number > highest:
                    highest = number

        return highest + 1

    def stabilize_camera(self, frames=30):
        # Discard frames to allow exposure and brightness
        # to stabilize
        for _ in range(frames):
            self.csi0.snapshot()
            time.sleep_ms(20)

        # Save a fresh background frame
        self._extra_fb.replace(self.csi0.snapshot())

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
