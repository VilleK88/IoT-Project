from src.NetworkManager import NetworkManager
from src.StorageConfig import StorageConfig
from src.FileManager import FileManager
from src.Camera import Camera

network_manager = NetworkManager()
network_manager.initialize()
storage_config = StorageConfig()
file_manager = FileManager(storage_config)
file_manager.initialize()

camera = Camera(storage_config, file_manager, network_manager)

network_manager.upload_mjpeg("/sdcard/motion_capture/video_00015.mjpeg")

"""while True:
    camera.update_frame_buffer()

    if camera.should_check_motion:
        if camera.thermal_detection():
            camera.record_video()"""
