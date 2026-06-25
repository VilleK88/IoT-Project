from src.Camera import Camera
import time
import omv

print(dir(omv))

camera = Camera()

last_save_time = time.ticks_ms()

while True:
    camera.update_frame_buffer()

    if camera.should_check_motion():
        if camera.detect_motion():
            print("motion detected")
            camera.record_video_with_prebuffer()
