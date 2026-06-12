import mjpeg
import csi
import machine
import os


class Camera:
    def __init__(self):
        self.csi0 = csi.CSI()
        self.csi0.reset()
        self.csi0.pixformat(csi.RGB565)
        self.csi0.framesize(csi.QVGA)
        print("camera created")

        self._led = machine.LED("LED_RED")
        print("Created a handle to the OpenMC red status LED")

        self._save_folder = "/sdcard/motion_capture"
        print("try to create a directory")
        try:
            os.mkdir(self._save_folder)
            print("directory created")

        except OSError as e:
            print("directory creation failed:", e)

        self._video_count = self.get_next_video_num()

        self._trigger_threshold = 5
        self._bg_update_frames = 50
        self._bg_update_blend = 128

        self._extra_fb = self.csi0.snapshot().copy()
        print("About to save background image...")
        self._extra_fb.replace(self.csi0.snapshot())
        print("Saved background image")
        self._triggered = False
        self._frame_count = 0

    def detect_motion(self):
        img = self.csi0.snapshot()

        self._frame_count += 1

        if self._frame_count > self._bg_update_frames:
            self._frame_count = 0
            img.blend(self._extra_fb, alpha=(255 - self._bg_update_blend))
            self._extra_fb.replace(img)

        img.difference(self._extra_fb)

        hist = img.get_histogram()
        diff = hist.get_percentile(0.99).l_value() - hist.get_percentile(0.90).l_value()

        self._triggered = diff > self._trigger_threshold

        return self._triggered

    def take_picture(self):
        img = self.csi0.snapshot()
        filename = "%s/pic_%05d.jpg" % (self._save_folder, self._video_count)
        img.save(filename)

    def record_video(self):
        print("start recording")
        filename = "%s/video_%05d.mjpeg" % (self._save_folder, self._video_count)
        print("Recording:", filename)
        video = mjpeg.Mjpeg(filename)
        self._led.on()
        for i in range(200):
            video.write(self.csi0.snapshot())
        video.close()
        self._video_count += 1
        self._led.off()
        print("record_video done")

    def get_next_video_num(self):
        highest = -1

        for filename in os.listdir(self._save_folder):
            if filename.startswith("video_") and filename.endswith(".mjpeg"):
                number_part = filename[6:-6]
                number = int(number_part)
                if number > highest:
                    highest = number
        return highest + 1
