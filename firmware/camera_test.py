import csi
import os

csi0 = csi.CSI()
csi0.reset()
csi0.pixformat(csi.RGB565)
csi0.framesize(csi.QVGA)

SAVE_FOLDER = "/sdcard/motion_capture"

try:
    os.mkdir(SAVE_FOLDER)
except OSError:
    pass

count = 0


def take_picture():
    global count

    img = csi0.snapshot()
    filename = "%s/pic_%05d.jpg" % (SAVE_FOLDER, count)
    img.save(filename)
    count += 1


while True:
    take_picture()
