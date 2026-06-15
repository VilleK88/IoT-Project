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

        self._video_folder = "/sdcard/motion_capture"
        self._image_folder = "/sdcard/motion_images"
        print("try to create a directory")
        self.create_directory(self._video_folder)
        self.create_directory(self._image_folder)

        self._video_count = self.get_next_file_num(self._video_folder, "video_", ".mjpeg")
        self._image_count = self.get_next_file_num(self._image_folder, "pic_", ".jpg")

        self._trigger_threshold = 15
        self._bg_update_frames = 50
        self._bg_update_blend = 128

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
        if self._frame_count > self._bg_update_frames:
            self._frame_count = 0

            bg_update = img.copy()
            bg_update.blend(self._extra_fb, alpha=(255 - self._bg_update_blend))

            self._extra_fb.replace(bg_update)

        diff = self.get_motion_diff(img)

        # Motion is detected when the difference exceeds
        # the configured threshold
        #print("diff:", diff)
        self._triggered = diff > self._trigger_threshold

        return self._triggered

    def take_picture(self):
        img = self.csi0.snapshot()
        filename = "%s/pic_%05d.jpg" % (self._image_folder, self._image_count)
        self._image_count += 1
        img.save(filename)

    def record_video(self):
        print("start recording")
        filename = "%s/video_%05d.mjpeg" % (self._video_folder, self._video_count)
        self._video_count += 1
        print("Recording:", filename)
        video = mjpeg.Mjpeg(filename)
        self._led.on()

        try:
            for i in range(500):
                video.write(self.csi0.snapshot())
        finally:
            video.close()
            self._led.off()

        print("record_video done")

        # Refresh the camera and background image after recording
        #self.stabilize_camera()
        self._frame_count = 0

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
        diff_img = img.copy()
        diff_img.difference(self._extra_fb)

        # Calculate the amount of motion from the difference image
        hist = diff_img.get_histogram()
        diff = hist.get_percentile(0.99).l_value() - hist.get_percentile(0.90).l_value()

        return diff
