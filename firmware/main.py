from src.NetworkManager import NetworkManager
from src.FileManager import FileManager
from src.LogManager import LogManager
from src.CameraPag import CameraPag
from src.CameraLepton import CameraLepton
from src.CameraManager import CameraManager
from src.Watchdog import Watchdog
import asyncio
import gc


async def main():
    # Garbage-collection threshold for the full system.
    gc.threshold(5_000_000)

    file_manager = FileManager()
    log_manager = LogManager(file_manager)
    network_manager = NetworkManager(file_manager, log_manager)

    network_manager.initialize()
    file_manager.initialize()
    log_manager.initialize()

    watchdog = Watchdog(log_manager)
    watchdog.log_boot_reason()

    camera_pag = CameraPag(log_manager)
    camera_lepton = CameraLepton(log_manager)
    camera_manager = CameraManager(file_manager, log_manager, watchdog, camera_pag, camera_lepton)

    await asyncio.gather(
        watchdog.watchdog_task(),
        camera_manager.update_frame_buffer_task(),
        camera_manager.monitor_motion_task(),
        #network_manager.upload_task()
    )

asyncio.run(main())
