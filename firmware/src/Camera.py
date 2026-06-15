from src.MotionConfig import MotionConfig
from src.StorageConfig import StorageConfig
import mjpeg
import csi
import machine
import os
import time


class Camera:
    def __init__(self):
        # Initialize the OpenMV N6 CSI camera interface
        self.csi0 = csi.CSI()
        self.csi0.reset()
        self.csi0.pixformat(csi.RGB565)
        self.csi0.framesize(csi.QVGA)

        # Status LED is used to indicat active recording
        self._led = machine.LED("LED_RED")

        # Load storage seggints and ensure output folders exist
        self._storage_config = StorageConfig()

        self.create_directory(self._storage_config.video_folder())
        self.create_directory(self._storage_config.image_folder())

        # Continue numbering from the highest existing file number
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

        # Load motion detection thresholds and timing settings
        self._motion_config = MotionConfig()

        # Background frame used for frame differencing
        self._extra_fb = self.csi0.snapshot().copy()

        # Allow the camera image to stabilize before capturing
        # the initial background frame
        time.sleep_ms(self._motion_config.stabilization_delay_ms())
        self.stabilize_camera(self._motion_config.stabilization_frames())

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

        # Build a unique filename using the configured folder, prefix and suffix
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

        # Build a unique filename using the configured folder, prefix and suffix
        filename = "%s/%s%05d%s" % (
            self._storage_config.video_folder(),
            self._storage_config.video_prefix(),
            self._video_count,
            self._storage_config.video_suffix()
        )

        # Increment immediately so a crash does not reuse the same filename
        self._video_count += 1
        print("Recording:", filename)
        video = mjpeg.Mjpeg(filename)

        # LED stays on while the camera is recording
        self._led.on()

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

        finally:
            # Always close the MJPEG file even if recording exits unexpectedly
            video.close()
            self._led.off()

        print("record_video done")

        # Short cooldown helps prevent immediate repeated recordings
        time.sleep_ms(self._motion_config.post_record_cooldown_ms())

        self._frame_count = 0

    def debug_record_video(self, duration_seconds=10):
        print("debug recording start")
        self._led.on()

        start_time = time.ticks_ms()

        try:
            while time.ticks_diff(time.ticks_ms(), start_time) < duration_seconds * self._motion_config.milliseconds_per_second():
                self.csi0.snapshot()

        finally:
            self._led.off()
        print("debug recording done")

    def get_next_file_num(self, directory, prefix, suffix):
        highest = self._storage_config.initial_file_number()

        for filename in os.listdir(directory):
            if filename.startswith(prefix) and filename.endswith(suffix):
                number_part = filename[len(prefix):-len(suffix)]
                number = int(number_part)
                if number > highest:
                    highest = number

        return highest + 1

    def stabilize_camera(self, frames):
        # Discard frames to allow exposure and brightness
        # to stabilize
        for _ in range(frames):
            self.csi0.snapshot()
            time.sleep_ms(self._motion_config.stabilization_frame_delay_ms())

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
