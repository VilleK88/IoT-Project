import mjpeg
import sensor
import time
import machine
import os


class Camera:
    def __init__(self):
        sensor.reset()
        sensor.set_pixformat(sensor.RGB565)
        sensor.set_framesize(sensor.QVGA)
        #sensor.skip_frames(time=2000)
        print("camera created")

        self.led = machine.LED("LED_RED")
        print("Created a handle to the OpenMC red status LED")

        self.save_folder = "/sdcard/motion_capture"
        print("try to create a directory")
        try:
            os.mkdir(self.save_folder)
            print("directory created")

        except OSError as e:
            print("directory creation failed:", e)

        self.video_count = self.get_next_video_num()

    def record_video(self):
        print("start recording")
        filename = "%s/video_%05d.mjpeg" % (self.save_folder, self.video_count)
        print("Recording:", filename)
        video = mjpeg.Mjpeg(filename)
        self.led.on()
        for i in range(200):
            video.write(sensor.snapshot())
        video.close()
        self.video_count += 1
        self.led.off()
        print("record_video done")

    def get_next_video_num(self):
        highest = -1

        for filename in os.listdir(self.save_folder):
            if filename.startswith("video_") and filename.endswith(".mjpeg"):
                number_part = filename[6:-6]
                number = int(number_part)
                if number > highest:
                    highest = number
        return highest + 1
