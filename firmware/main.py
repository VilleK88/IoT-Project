from src.Camera import Camera

camera = Camera()

while True:
    if camera.detect_motion():
        print("motion detected")
        camera.record_video()
