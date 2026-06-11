import sensor
import mjpeg
import machine
import os

sensor.reset()
sensor.set_pixformat(sensor.RGB565)
sensor.set_framesize(sensor.QVGA)
sensor.skip_frames(time=2000)

led = machine.LED("LED_RED")
led.on()

SAVE_FOLDER = "/sdcard/motion_capture"

try:
    os.mkdir(SAVE_FOLDER)
except OSError:
    pass

count = 0


def record_video():
    global count

    filename = "%s/video_%05d.mjpeg" % (SAVE_FOLDER, count)
    m = mjpeg.Mjpeg(filename)
    for i in range(200):
        m.write(sensor.snapshot())
    count += 1
    m.close()
    led.off()


while True:
    record_video()
