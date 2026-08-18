from src.StorageConfig import StorageConfig
from src.BufferConfig import BufferConfig
from src.MotionConfig import MotionConfig
from src.Tools import Tools
from src.CameraPag import CameraPag
from src.CameraLepton import CameraLepton
import csi
import mjpeg
import time
import machine
import imu
import asyncio
import gc

class CameraManager:
    def __init__(self,
                 file_manager,
                 log_manager,
                 watchdog,
                 camera_pag,
                 camera_lepton):

        self._storage_config = StorageConfig()
        self._buf_config = BufferConfig()
        self._mot_conf = MotionConfig()
        self._file_manager = file_manager
        self._log_manager = log_manager
        self._watchdog = watchdog
        self._tools = Tools()

        # Recording state
        self._led = machine.LED("LED_RED")

        self._camera_pag = camera_pag
        self._tools.print_memory_status("After PAG7936 init")
        self._camera_lepton = camera_lepton
        self._tools.print_memory_status("After Lepton init")

    async def update_frame_buffer_task(self):
        await asyncio.gather(
            self._camera_pag.update_frame_buffer_pag(),
            self._camera_lepton.update_frame_buffer_lepton()
        )

    # Returns True when it is time to perform the next motion check.
    async def monitor_motion(self):
        while True:
            # Do not perform frame differencing during or immediately after FFC.
            if not self._camera_lepton.handle_ffc():
                if await self._camera_lepton.detect_motion_async_lepton():
                    print("camera.record_video()")
                    if self._file_manager.video_space_available():
                        self._log_manager.info("Video recording started")
                        try:
                            self.record_video_and_monitor()
                            self._log_manager.info("Video recording completed")
                        except Exception as err:
                            self._log_manager.error("Video recording failed: {}".format(err))
                            raise
                    else:
                        print("Video storage quota reached")
                        self._log_manager.warning("Video storage quota reached")
            await asyncio.sleep_ms(self._mot_conf.chk_mot_ms())

    # Records an MJPEG video beginning with the buffered frames
    # followed by live RGB frames.
    def record_video_and_monitor(self):
        self._tools.print_memory_status("Memory before recording")
        self._log_manager.info(
            "Memory before recording: {}".format(gc.mem_free())
        )

        # Create a new MJPEG file and prepare the camera for recording.
        filename_pag, video_pag = self.create_motion_video(
            self._storage_config.video_prefix_pag(),
            self._camera_pag.cam_config.recording_width_pag(),
            self._camera_lepton.cam_config.recording_height_pag(),
        )
        filename_lepton, video_lepton = self.create_motion_video(
            self._storage_config.video_prefix_lepton(),
            self._camera_pag.cam_config.width_lepton(),
            self._camera_lepton.cam_config.height_lepton()
        )
        # Reserve the next video number for future recordings.
        self._file_manager.increase_video_count()

        saved_frames_pag = 0
        saved_frames_lepton = 0

        try:
            # Write the buffered RGB frames before switching the PAG7936 to HD mode.
            saved_frames_pag = (self._camera_pag.write_prebuffer_with_catchup_pag(video_pag))
            saved_frames_lepton = (self._camera_lepton.write_prebuffer_with_catchup_lepton(video_lepton))

            self.start_recording_state()

            last_live_frame_time = time.ticks_ms()
            last_motion_check = time.ticks_ms()
            recording_start_time = time.ticks_ms()
            last_motion_time = time.ticks_ms()
            last_watchdog_feed = time.ticks_ms()

            live_frames_pag = 0
            live_recording_start = time.ticks_ms()

            # Continue recording RGB frames until no motion is detected or the maximum recording time is reached.
            while time.ticks_diff(time.ticks_ms(), recording_start_time) < self._camera_pag.cam_config.max_recording_time_ms():
                now = time.ticks_ms()

                if time.ticks_diff(now, last_watchdog_feed) >= self._watchdog.feed_interval_ms():
                    self._watchdog.feed()
                    last_watchdog_feed = now

                # Maintain the configured recording frame rate.
                if time.ticks_diff(now, last_live_frame_time) >= self._camera_pag._frame_interval_ms_pag:
                    last_live_frame_time = now

                    img_pag = self._camera_pag.csi0.snapshot()  # Capture the next RGB frame.
                    img_lepton = self._camera_lepton.csi1.snapshot()

                    self._camera_pag._current_frame_pag = img_pag
                    self._camera_lepton._current_frame_lepton = img_lepton

                    video_pag.write(img_pag)  # Append the frame to the MJPEG video.
                    video_lepton.write(img_lepton)

                    saved_frames_pag += 1
                    saved_frames_lepton += 1

                    live_frames_pag += 1

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
        finally:
            live_recording_duration = time.ticks_diff(
                time.ticks_ms(),
                live_recording_start
            )

            actual_fps = 0
            if live_recording_duration > 0:
                actual_fps = (
                        live_frames_pag * 1000 / live_recording_duration
                )
            print(
                "LIVE PAG:",
                live_frames_pag,
                "frames,",
                live_recording_duration,
                "ms, FPS:",
                actual_fps
            )

            self._log_manager.info(
                "LIVE PAG: {} frames, {} ms, FPS: {}".format(
                    live_frames_pag,
                    live_recording_duration,
                    actual_fps
                )
            )

            video_pag.close() # Always close the MJPEG file, even if recording exits unexpectedly.
            video_lepton.close()
            self._led.off()  # Turn off the recording status LED.

            # Update the MJPEG timing so playback matches the original capture rate.
            duration_ms_pag = saved_frames_pag * self._camera_pag._frame_interval_ms_pag
            duration_ms_lepton = saved_frames_lepton * self._camera_lepton._frame_interval_ms_lepton

            self._file_manager.patch_mjpeg_timing(filename_pag, saved_frames_pag, duration_ms_pag)
            self._file_manager.patch_mjpeg_timing(filename_lepton, saved_frames_lepton, duration_ms_lepton)
            self._file_manager.patch_mjpeg_index(filename_pag)
            self._file_manager.patch_mjpeg_index(filename_lepton)

            self._tools.print_memory_status("record_video_with_prebuffer done. Memory After cleanup")
            self._log_manager.info(
                "Memory after recording: {}".format(gc.mem_free())
            )
            self.stop_recording_state()  # Restore the default camera state after recording.

    # Enables the hardware and camera settings required for recording.
    def start_recording_state(self):
        self._led.on()  # Turn on the recording status LED.
        self._camera_pag.csi0.framesize(csi.HD)  # 1280x800
        print("CSI resolution:", self._camera_pag.csi0.width(), self._camera_pag.csi0.height())

    # Restores the camera state after recording has finished.
    def stop_recording_state(self):
        # Remove any buffered frames so the next recording starts with
        # a fresh circular buffer.
        self._camera_pag._buf_index_pag, self._camera_pag._last_frame_time_pag = self.clear_frame_buffer(
            self._camera_pag._buffer_pag,
            self._camera_pag._buf_index_pag,
            self._camera_pag._last_frame_time_pag
        )
        self._camera_lepton._buf_index_lepton, self._camera_lepton._last_frame_time_lepton = self.clear_frame_buffer(
            self._camera_lepton._buffer_lepton,
            self._camera_lepton._buf_index_lepton,
            self._camera_lepton._last_frame_time_lepton
        )
        self._camera_pag.csi0.framesize(csi.VGA)  # PAG7936 output: 640x400

    # Creates a new MJPEG file for motion recording.
    def create_motion_video(self, prefix, this_width : int, this_height : int):
        # Build a unique filename using the configured folder, prefix,
        # suffix and the next available video number.
        filename = self._file_manager.build_filename(
            self._storage_config.vid_dir(),
            prefix,
            self._storage_config.vid_suffix(),
            self._file_manager.get_video_count()
        )
        print("Recording:", filename)
        # Create and return the MJPEG video object.
        video = mjpeg.Mjpeg(filename, width=this_width, height=this_height)
        return filename, video

    # Clears the circular frame buffer after recording.
    def clear_frame_buffer(self, this_buffer, this_index, this_frame_time):
        for i in range(self._buf_config.buf_size()):
            this_buffer[i] = None
        this_index = 0
        this_frame_time = time.ticks_ms()
        return this_index, this_frame_time