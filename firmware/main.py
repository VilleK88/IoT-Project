from src.Camera import Camera
import gc
import time

print("memory at start:", gc.mem_free())
camera = Camera()
print("memory after Camera has been constructed:", gc.mem_free())

last_save_time = time.ticks_ms()

while True:
    camera.update_frame_buffer()

    if camera.should_check_motion():
        if camera.detect_motion():
            print("motion detected")
            camera.record_video_with_prebuffer()
