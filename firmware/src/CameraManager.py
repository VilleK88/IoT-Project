from src.StorageConfig import StorageConfig
from src.MotionConfig import MotionConfig
from src.Tools import Tools
import time
import machine
import asyncio
import gc

class RecordState:
    PREPARE = 0
    PREBUFFER = 1
    RECORDING = 2
    FINALIZING = 3

class CameraManager:
    def __init__(self,
                 file_manager,
                 log_manager,
                 watchdog,
                 camera_pag,
                 camera_lepton):

        self._record_state = RecordState.PREPARE

        self._state_handlers = {
            RecordState.PREPARE: self.prepare_state,
            RecordState.PREBUFFER: self.prebuffer_state,
            RecordState.RECORDING: self.recording_state,
            RecordState.FINALIZING: self.finalizing_state,
        }

        self._storage_config = StorageConfig()
        self._mot_conf = MotionConfig()
        self._file_manager = file_manager
        self._log_manager = log_manager
        self._watchdog = watchdog
        self._tools = Tools()

        # Recording state
        self._led = machine.LED("LED_RED")

        self._camera_pag = camera_pag
        self._camera_lepton = camera_lepton

        self._live_recording_start = 0

    async def update_frame_buffer_task(self):
        await asyncio.gather(
            self._camera_pag.update_frame_buffer_pag(),
            self._camera_lepton.update_frame_buffer_lepton()
        )

    # Returns True when it is time to perform the next motion check.
    async def monitor_motion_task(self):
        while True:
            # Do not perform frame differencing during or immediately after FFC.
            if not self._camera_lepton.handle_ffc():
                if await self._camera_lepton.detect_motion_async_lepton():
                    print("camera.record_video()")
                    if self._file_manager.video_space_available():
                        self._log_manager.info("Video recording started")
                        try:
                            self.record_state_machine()
                            self._log_manager.info("Video recording completed")
                        except Exception as err:
                            self._log_manager.error("Video recording failed: {}".format(err))
                            raise
                    else:
                        print("Video storage quota reached")
                        self._log_manager.warning("Video storage quota reached")
            await asyncio.sleep_ms(self._mot_conf.chk_mot_ms())

    def record_state_machine(self):
        try:
            while True:
                handler = self._state_handlers[self._record_state]
                self._record_state = handler()
                if self._record_state == RecordState.PREPARE:
                    break
        except Exception as err:
            self._log_manager.error("Recording state machine failed: {}".format(err))
            print("Recording state machine failed:",err)
            raise
        finally:
            self._record_state = RecordState.PREPARE

    def prepare_state(self):
        print("prepare state")
        # Create a new MJPEG files and prepare the cameras for recording.
        self._camera_pag.prepare_video(self._file_manager)
        self._camera_lepton.prepare_video(self._file_manager)
        # Reserve the next video number for future recordings.
        self._file_manager.increase_video_count()
        return RecordState.PREBUFFER

    def prebuffer_state(self):
        print("prebuffer state")
        # Write the buffered RGB frames before switching the PAG7936 to HD mode.
        self._camera_pag.write_prebuffer_with_catchup_pag(),
        self._camera_lepton.write_prebuffer_with_catchup_lepton()
        return RecordState.RECORDING

    def recording_state(self):
        print("recording state")
        self.start_recording_state()

        recording_start_time = time.ticks_ms()
        last_watchdog_feed = time.ticks_ms()
        last_live_frame_time = time.ticks_ms()
        last_motion_check = time.ticks_ms()
        last_motion_time = time.ticks_ms()

        self._camera_pag.live_frames_pag = 0
        self._live_recording_start = time.ticks_ms()

        # Continue recording frames until no motion is detected or the maximum recording time is reached.
        while (time.ticks_diff(time.ticks_ms(),
                              recording_start_time) <
               self._camera_pag.cam_config.max_recording_time_ms()):

            now = time.ticks_ms()

            if time.ticks_diff(now, last_watchdog_feed) >= self._watchdog.feed_interval_ms():
                self._watchdog.feed()
                last_watchdog_feed = now

            # Maintain the configured recording frame rate.
            if time.ticks_diff(now, last_live_frame_time) >= self._camera_pag.frame_interval_ms():
                last_live_frame_time = now

                self._camera_pag.record_frame()
                self._camera_lepton.record_frame()

                self._camera_pag.live_frames_pag += 1

                # Check for movement at the configured interval.
                if time.ticks_diff(now, last_motion_check) >= self._mot_conf.chk_mot_ms():
                    last_motion_check = now
                    # Ignore thermal motion detection during or immediately after FFC.
                    if not self._camera_lepton.handle_ffc():
                        # Reset the no-motion timer whenever movement is detected.
                        if self._camera_lepton.detect_motion_lepton():
                            last_motion_time = now
                        # Stop recording after the configured period without movement.
                        elif time.ticks_diff(now, last_motion_time) >= self._mot_conf.motion_timeout_ms():
                            break
                    else:
                        last_motion_time = now

        return RecordState.FINALIZING

    def finalizing_state(self):
        print("finalizing state")

        live_recording_duration = time.ticks_diff(
            time.ticks_ms(),
            self._live_recording_start
        )

        actual_fps = 0
        if live_recording_duration > 0:
            actual_fps = (
                    self._camera_pag.live_frames_pag * 1000 / live_recording_duration
            )

        print("LIVE PAG:", self._camera_pag.live_frames_pag,
            "frames,", live_recording_duration,
            "ms, FPS:", actual_fps
        )
        self._log_manager.info(
            "LIVE PAG: {} frames, {} ms, FPS: {}".format(
                self._camera_pag.live_frames_pag,
                live_recording_duration,
                actual_fps
            )
        )

        self._led.off()
        self._camera_pag.finalize_video(self._file_manager)
        self._camera_lepton.finalize_video(self._file_manager)

        self._tools.print_memory_status("record_video_with_prebuffer done. Memory After cleanup")
        self._log_manager.info(
            "Memory after recording: {}".format(gc.mem_free())
        )
        self.stop_recording_state()  # Restore the default camera state after recording.
        return RecordState.PREPARE

    # Enables the hardware and camera settings required for recording.
    def start_recording_state(self):
        self._led.on()  # Turn on the recording status LED.
        self._camera_pag.start_recording_mode()
        print("CSI resolution:", self._camera_pag.csi0.width(), self._camera_pag.csi0.height())

    # Restores the camera state after recording has finished.
    def stop_recording_state(self):
        # Remove any buffered frames so the next recording starts with
        # a fresh circular buffer.
        self._camera_pag.clear_frame_buffer()
        self._camera_lepton.clear_frame_buffer()
        self._camera_pag.stop_recording_mode()