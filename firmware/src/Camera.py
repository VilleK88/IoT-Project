import mjpeg
import sensor
import machine
import os


class Camera:
    def __init__(self):
        sensor.reset()
        sensor.set_pixformat(sensor.RGB565)
        sensor.set_framesize(sensor.QVGA)
        sensor.skip_frames(time=2000)

        self.led = machine.LED("LED_RED")
        self.led.on()

        self.SAVE_FOLDER = "/sdcard/motion_capture"

        try:
            os.mkdir(self.SAVE_FOLDER)
        except OSError:
            pass

        self.video_count = 0

    def record_video(self):
        filename = "%s/video_%05d.mjpeg" % (self.SAVE_FOLDER, self.video_count)
        m = mjpeg.Mjpeg(filename)
        for i in range(200):
            m.write(sensor.snapshot())
        self.video_count += 1
        m.close()
        self.led.off()
