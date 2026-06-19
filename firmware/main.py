from src.Camera import Camera
import gc
import time

print("memory at start:", gc.mem_free())
camera = Camera()
print("memory after Camera has been constructed:", gc.mem_free())

last_save_time = time.ticks_ms()

while True:
    img = camera.csi0.snapshot()

    camera.update_frame_buffer(img)

    now = time.ticks_ms()
    if time.ticks_diff(now, last_save_time) >= 10000:
        camera.save_buf_as_mjpeg()
        last_save_time = now

    if camera.should_check_motion():
        if camera.detect_motion(img):
            print("motion detected")
