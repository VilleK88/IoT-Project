from src.NetworkManager import NetworkManager
from src.StorageConfig import StorageConfig
from src.FileManager import FileManager
from src.LogManager import LogManager
from src.Camera import Camera
from src.Watchdog import Watchdog
import asyncio

import gc
gc.threshold(10_000_000)
print(gc.threshold())

async def main():
    storage_config = StorageConfig()
    file_manager = FileManager(storage_config)
    log_manager = LogManager(file_manager)
    network_manager = NetworkManager(file_manager, log_manager)

    network_manager.initialize()
    file_manager.initialize()
    log_manager.initialize()

    watchdog = Watchdog(log_manager)
    watchdog.log_boot_reason()

    camera = Camera(storage_config, file_manager, network_manager, log_manager, watchdog)

    await asyncio.gather(
        watchdog.watchdog_task(),
        camera.update_frame_buffer_pag(),
        camera.update_frame_buffer_lepton(),
        camera.monitor_motion(),
        #network_manager.upload_task()
    )

asyncio.run(main())
