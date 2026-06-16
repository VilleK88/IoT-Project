from src.Camera import Camera
import gc

print("memory at start:", gc.mem_free())
camera = Camera()
print("memory after Camera has been constructed:", gc.mem_free())

while True:
    if camera.detect_motion():
        print("motion detected")
        #camera.record_video()
        camera.write_to_memory_stream()
