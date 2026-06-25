from src.StorageConfig import StorageConfig
from src.FileManager import FileManager
from src.Camera import Camera
import time

storage_config = StorageConfig()
file_manager = FileManager(storage_config)
file_manager.prepare_directories()
file_manager.load_file_counters()

camera = Camera(storage_config, file_manager)

last_save_time = time.ticks_ms()

while True:
    camera.update_frame_buffer()

    if camera.should_check_motion():
        if camera.detect_motion():
            print("motion detected")
            camera.record_video_with_prebuffer()
