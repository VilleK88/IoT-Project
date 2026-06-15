from src.Camera import Camera
import time

camera = Camera()

while True:
    if camera.detect_motion():
        print("motion detected")
        camera.record_video()
        time.sleep_ms(1000)
