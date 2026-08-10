from src.NetworkManager import NetworkManager
from src.StorageConfig import StorageConfig
from src.FileManager import FileManager
from src.Camera import Camera
from src.Watchdog import Watchdog
import asyncio


async def main():
    storage_config = StorageConfig()
    file_manager = FileManager(storage_config)
    network_manager = NetworkManager(file_manager)
    network_manager.initialize()
    file_manager.initialize()

    camera = Camera(storage_config, file_manager, network_manager)

    await asyncio.gather(
        camera.update_frame_buffer_pag(),
        camera.monitor_motion(),
        network_manager.upload_task()
    )

asyncio.run(main())
