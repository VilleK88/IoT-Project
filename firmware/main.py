from src.StorageConfig import StorageConfig
from src.FileManager import FileManager
from src.Camera import Camera

storage_config = StorageConfig()
file_manager = FileManager(storage_config)
file_manager.prepare_directories()
file_manager.load_file_counters()

camera = Camera(storage_config, file_manager)

while True:
    camera.update_frame_buffer()

    if camera.should_check_motion:
        if camera.thermal_detection():
            camera.record_video()
