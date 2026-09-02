from src.CameraBase import Camera
import csi
import time
import image
import ustruct
import asyncio
import gc

class CameraLepton(Camera):
    def __init__(self, log_manager):
        super().__init__()
        self.name = "Lepton-3.5"

        self._log_manager = log_manager

        self._last_motion_check_time = time.ticks_ms()
        self._frame_count = 0

        # Initialize the FLIR Lepton thermal camera second.
        # Use a soft reset so the already initialized PAG7936 remains active.
        self.csi1 = csi.CSI(cid=csi.LEPTON, stream=False)
        self.csi1.reset(hard=False)  # Soft reset and initialize the sensor
        self.csi1.pixformat(csi.GRAYSCALE)  # Set pixel format to GRAYSCALE
        self.csi1.framesize(csi.QQVGA)  # Native Lepton resolution: 160x120

        #self.csi1.vflip(True)
        #self.csi1.auto_rotation(True)

        # Enable radiometric measurement mode and map the grayscale output
        # to the configured temperature range.
        self.csi1.ioctl(csi.IOCTL_LEPTON_SET_MODE, True, False)
        self.csi1.ioctl(
            csi.IOCTL_LEPTON_SET_RANGE,
            self._mot_conf.min_temp_in_celsius(),
            self._mot_conf.max_temp_in_celsius()
        )

        # Allow the Lepton to stabilize before capturing the initial
        # background image used by thermal frame differencing.
        self._current_frame = (
            self.csi1.snapshot(time=self.cam_config.lepton_stabilization_ms())
        )

        self._extra_fb = image.Image(self.csi1.width(), self.csi1.height(), self.csi1.pixformat())
        print("About to save background image...")
        self._extra_fb.draw_image(self.csi1.snapshot())
        print("Saved background image - Now frame differencing!")

        self._ffc_active = False
        self._ffc_recovery_until = None
        self._last_ffc_check_time = 0
        self._ffc_check_interval_ms = 1000
        self._ffc_recalibration_time_ms = 5000

        self.filename_lepton = None
        self.video_lepton = None
        self.saved_frames = 0

        self._tools.print_memory_status("After Lepton init")

    def write_to_lepton(self, frame):
        try:
            self.video_lepton.write(frame)
        except Exception as error:
            self._log_manager.error("SD card write failed: {}".format(error))
            raise

    def record_frame(self):
        self._current_frame = self.csi1.snapshot()
        self.write_to_lepton(self._current_frame)
        self.saved_frames += 1

    # Thermal frame differencing.
    def detect_motion_lepton(self):
        img = self._current_frame
        if img:
            self._frame_count += 1
            if self._frame_count > self._mot_conf.bg_update_frames():
                self._frame_count = 0
                img.blend(self._extra_fb, alpha=(255 - self._mot_conf.bg_update_blend()))
                self._extra_fb.draw_image(img)
            img.difference(self._extra_fb)
            hist = img.get_histogram()
            diff = (hist.get_percentile(
                self._mot_conf.hist_high_percentile()).l_value -
                    hist.get_percentile(self._mot_conf.hist_low_percentile()).l_value)
            return diff > self._mot_conf.trigger_threshold()
        return False

    async def detect_motion_async_lepton(self):
        img = self._current_frame
        if img:
            self._frame_count += 1
            if self._frame_count > self._mot_conf.bg_update_frames():
                self._frame_count = 0
                img.blend(self._extra_fb, alpha=(255 - self._mot_conf.bg_update_blend()))
                self._extra_fb.draw_image(img)
            # Compare the current temperature-filtered frame against the
            # temperature-filtered background frame.
            img.difference(self._extra_fb)
            hist = img.get_histogram()
            diff = (hist.get_percentile(
                self._mot_conf.hist_high_percentile()).l_value -
                    hist.get_percentile(self._mot_conf.hist_low_percentile()).l_value)
            return diff > self._mot_conf.trigger_threshold()
        return False

    def write_prebuffer_with_catchup_lepton(self):
        last_live_frame_time_lepton = time.ticks_ms()

        self.saved_frames = 0

        # Retrieve the buffered frames in chronological order.
        prebuf_frames_lepton, self._buffer_index = (
            self.get_ordered_buf_frames(self._buffer, self._buffer_index)
        )

        # Stores frames captured while the pre-buffer is being written.
        # These frames are appended afterwards to reduce the recording gap.
        catchup_frames_lepton = []

        # Write the buffered frames to the MJPEG file.
        for frame in prebuf_frames_lepton:
            self.write_to_lepton(frame)
            self.saved_frames += 1
            now = time.ticks_ms()
            if time.ticks_diff(now, last_live_frame_time_lepton) >= self._frame_interval_ms:
                self._current_frame = self.csi1.snapshot()
                catchup_frames_lepton.append(self._current_frame.copy())
                last_live_frame_time_lepton = now

        # Append the frames captured during the pre-buffer write so the
        # transition from buffered video to live recording is as seamless as possible.
        for frame in catchup_frames_lepton:
            self.write_to_lepton(frame)
            self.saved_frames += 1

    async def update_frame_buffer_lepton(self):
        while True:
            self._current_frame = await self._snapshot_async(self.csi1)
            self._buffer_index = (
                self._save_frame(
                    self._current_frame.copy(),
                    self._buffer,
                    self._buffer_index,
                )
            )
            await asyncio.sleep_ms(self._buf_config.frame_interval_ms())

    # FFC (Flat-Field Correction) is an internal calibration process performed
    # periodically by the FLIR Lepton thermal camera to compensate for sensor drift.
    # FFC temporarily changes the thermal image and can therefore create large
    # differences between consecutive frames, which frame-difference motion
    # detection could incorrectly interpret as movement.
    #
    # The functions below monitor the Lepton FFC state, suspend thermal motion
    # detection while calibration is active, wait for the image to stabilize,
    # and then replace the old frame-difference background with a new reference.
    def get_ffc_status(self):
        # Read the Lepton FFC status attribute.
        # 0x0244 identifies the FFC status attribute and 2 requests
        # two 16-bit words (32 bits) from the Lepton.
        data = self.csi1.ioctl(csi.IOCTL_LEPTON_GET_ATTRIBUTE, 0x0244, 2)
        # Convert the four returned bytes into a 32-bit little-endian integer.
        return ustruct.unpack("<I", data)[0]

    def handle_ffc(self):
        # Return True whenever thermal motion detection should be skipped.
        # This includes the FFC itself and the post-FFC stabilization period.
        now = time.ticks_ms()
        # This method may be called several times per second by motion detection,
        # but query the Lepton FFC status only once per configured interval.
        if time.ticks_diff(now, self._last_ffc_check_time) >= self._ffc_check_interval_ms:
            self._last_ffc_check_time = now
            ffc_status = self.get_ffc_status()
            # A non-zero status means that the Lepton is currently performing FFC.
            # Motion detection must be skipped because FFC changes the thermal image
            # and could otherwise be interpreted as movement.
            if ffc_status != 0:
                if not self._ffc_active:
                    self._ffc_active = True
                return True

            # If FFC was active during the previous poll but is no longer active,
            # the calibration has just finished.
            if self._ffc_active:
                self._ffc_active = False
                # Give the thermal image five seconds to stabilize before
                # allowing frame differencing to resume.
                self._ffc_recovery_until = time.ticks_add(now, self._ffc_recalibration_time_ms)
                return True
        # FFC status is polled less frequently than this method is called.
        # Keep motion detection disabled between polls while the last known
        # Lepton state says that FFC is still active.
        if self._ffc_active:
            return True
        # Keep motion detection disabled during the post-FFC recovery period
        if self._ffc_recovery_until is not None:
            if time.ticks_diff(self._ffc_recovery_until, now) > 0:
                return True
            # Recovery has finished. The old background frame was captured
            # before FFC and is no longer a reliable reference. Replace it
            # with the latest stabilized thermal frame.
            self._extra_fb.draw_image(self._current_frame)
            self._ffc_recovery_until = None
            # Restart the periodic background-update counter because a new
            # frame-difference reference has just been established.
            self._frame_count = 0
            # Skip the current motion check because the current thermal frame
            # has just been installed as the new frame-difference background.
            return True
        # False means that no FFC or recovery is active and thermal
        # frame-difference motion detection can safely proceed.
        return False

    def prepare_video(self, file_manager):
        # Create a new MJPEG file and prepare the camera for recording.
        self.filename_lepton, self.video_lepton = self.create_motion_video(
            file_manager,
            self._storage_config.video_prefix_lepton(),
            self.cam_config.width_lepton(),
            self.cam_config.height_lepton()
        )

    def finalize_video(self, file_manager):
        self.video_lepton.close()
        duration_ms = self.saved_frames * self.frame_interval_ms()
        file_manager.patch_mjpeg_timing(
            self.filename_lepton,
            self.saved_frames,
            duration_ms
        )
        file_manager.patch_mjpeg_index(self.filename_lepton)

    def buffer(self):
        return self._buffer

    def buffer_index(self):
        return self._buffer_index

    def last_frame_time(self):
        return self._last_frame_time

    def frame_interval_ms(self):
        return self._frame_interval_ms

    def ring_buffer_fill_count(self):
        return self._ring_buf_fil_count