from src.Camera import Camera
#import os
#import machine
#import vfs

TRIGGER_TRESHOLD = 5
BG_UPDATE_FRAMES = 50
BG_UPDATE_BLEND = 128

print("start creating the camera")
camera = Camera()
print("camera created")
camera.record_video()
print("video recorded")
