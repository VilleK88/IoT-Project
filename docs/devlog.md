
## 2026-06-11
### Initial Hardware Setup

* Received OpenMV N6 development board.
* Installed OpenMV IDE and verified board connectivity.
* Verified camera module operation using built-in example scripts.

### microSD Card Investigation

* Installed bundled microSD card.
* Discovered existing project data on the card, including images, configuration files, Wi-Fi credentials, TLS certificate, and device identifiers.
* Determined that the card had likely been used in a previous OpenMV project.
* Cleared the card for project use.

### OpenMV Exploration

* Learned the basic OpenMV development workflow.
* Investigated internal flash storage and microSD storage usage.
* Learned that applications are primarily developed using MicroPython.

### Camera Testing

* Tested multiple built-in OpenMV example scripts.
* Investigated face detection example failure.
* Encountered missing resource error:

  * OSError: [Errno 2] ENOENT
* Determined that some examples require additional files that are not present on the device.

### Performance Investigation

* Observed IDE freezing during continuous FPS output.
* Captured terminal logs showing corrupted serial output before freezing.
* Investigated possible causes including serial output overload, USB communication issues, and IDE communication handling.

### Debugging

Initial test:

* Continuous FPS printing using `print(clock.fps())`.
* IDE eventually froze.

Second test:

* Continuous image capture using `sensor.snapshot()` without FPS output.
* System remained stable.

### Key Findings

* OpenMV N6 applications are developed using MicroPython.
* Continuous serial output can significantly affect IDE responsiveness.
* OpenMV IDE framebuffer introduces measurable overhead during live image streaming.
* Camera capture remains stable when serial output is minimized.

### Repository Setup

* Created GitHub repository for the IoT project.
* Added initial project documentation and devlog infrastructure.
* Began maintaining project progress through version control.

## 2026-06-11
### OpenMV Project Structure and Deployment

- Continued restructuring the OpenMV firmware code into a more maintainable project layout.
- Created a dedicated `firmware` folder for OpenMV N6 code.
- Added a `src` folder for separating classes and reusable modules from `main.py`.
- Started moving camera recording logic toward a class-based structure.

### MJPEG Recording Investigation

- Tested OpenMV MJPEG video recording.
- Confirmed that MJPEG files can be recorded to the microSD card.
- Verified that recorded MJPEG files can be opened with VLC.
- Observed that VLC may show an index warning, but the video still plays correctly.

### File System and Deployment Findings

- Confirmed that OpenMV N6 does not automatically import modules from the PC-side GitHub repository.
- Learned that required Python modules must also exist on the OpenMV device filesystem.
- Identified that `firmware/src` must be copied to the OpenMV drive for imports such as `from src.Camera import Camera` to work.

### Deployment Automation

- Created a Windows `deploy.bat` script to automate copying firmware files to the OpenMV drive.
- The deployment script copies `firmware/main.py` to the OpenMV root.
- The deployment script copies the full `firmware/src` folder to the OpenMV filesystem.
- This removes the need to manually copy files after each code change.

## 2026-06-12
### SD Card Debugging

- Investigated repeated failures when saving MJPEG recordings to the microSD card.
- Added filesystem diagnostics to verify available storage devices and mount points.
- Confirmed that OpenMV only exposed `rom` and `flash` when the original microSD card was inserted.
- Observed repeated `OSError: [Errno 19] ENODEV` errors when attempting to access `/sdcard`.
- Verified that the issue was unrelated to the Camera class refactor, deployment workflow, or import structure.

### Internal Flash Recovery

- Used the OpenMV IDE "Erase Internal FAT File System" tool.
- Restored normal startup behavior, including the expected blue LED boot indication.
- Confirmed that the internal flash filesystem remained accessible after recovery.

### SD Card Investigation

- Tested a second microSD card.
- Confirmed that OpenMV correctly detected the replacement card.
- Verified that `/sdcard` became available and accessible through MicroPython.
- Determined that the original microSD card is likely corrupted, incompatible, or otherwise unreadable by the OpenMV firmware.

### Camera Class Refactor

- Continued moving camera functionality from `main.py` into a dedicated `Camera` class.
- Encapsulated MJPEG video recording functionality inside `Camera.record_video()`.
- Added automatic creation of the `motion_capture` directory on the microSD card.
- Added logic to determine the next available video number by scanning existing recordings.
- Implemented persistent video numbering across device restarts.

### MJPEG Recording Validation

- Successfully recorded MJPEG video files using the refactored Camera class.
- Verified that recordings are written to `/sdcard/motion_capture`.
- Added recording path diagnostics to simplify future debugging.
- Confirmed successful end-to-end recording workflow using the replacement microSD card.

## 2026-06-12
### CSI Camera Migration

- Migrated the Camera class from the legacy `sensor` API to the newer CSI camera interface.
- Replaced sensor-based camera initialization with a dedicated `csi.CSI()` instance.
- Updated camera configuration and image capture calls to use CSI methods.
- Verified that MJPEG video recording continues to function correctly after the migration.
- Confirmed successful video creation on the microSD card using the CSI backend.

## 2026-06-12
### microSD Card Recovery

- Used a microSD card reader for troubleshooting.
- Reformatted the original microSD card using a PC.
- Reinserted the card into the OpenMV N6 and verified successful detection by the firmware.
- Confirmed that `/sdcard` is mounted and accessible through MicroPython.
- Verified successful creation and access of the `motion_capture` directory.

### Recording Validation

- Tested Camera class functionality using the recovered microSD card.
- Confirmed that MJPEG recordings can be created successfully on the restored card.
- Verified end-to-end operation of the recording pipeline after storage recovery.

## 2026-06-12
### Motion Detection Implementation

- Migrated motion detection logic from the legacy sensor API to the CSI camera API.
- Replaced legacy frame buffer allocation approach with CSI-compatible image storage.
- Implemented frame differencing using a background image stored in RAM.
- Added automatic background image initialization during Camera startup.
- Verified histogram-based motion detection logic using CSI camera frames.
- Confirmed successful motion detection operation on the OpenMV N6.

## 2026-06-15
### OpenMV N6 USB Connectivity Troubleshooting

- Investigated an issue where the OpenMV N6 was not detected by OpenMV IDE or Windows Device Manager.
- Confirmed that the board was receiving power, indicated by the red power LED.
- Tested the newly purchased USB-A to USB-C cable with a mobile phone and verified that the cable supports data transfer.
- Determined that the issue was not caused by the OpenMV N6 board or the USB cable.
- Isolated the problem to the existing Logik USB hub.
- Confirmed that the OpenMV N6 is detected correctly when connected directly to the laptop's USB-A port.
- Successfully re-established communication with OpenMV IDE using a direct USB connection.
- Development can continue without hardware changes by connecting the board directly to the laptop.

### Notes

- Current USB hub appears incompatible with the OpenMV N6 despite providing power.
- Future upgrade planned to a higher-quality USB 3.x hub with both USB-A and USB-C ports.

## 2026-06-15
### OpenMV N6 Camera Focus and USB Troubleshooting

- Troubleshot OpenMV N6 USB connectivity issue.
- Verified that the USB-A to USB-C cable supports data transfer by testing it with a mobile phone.
- Confirmed that the issue was caused by the USB hub, not the OpenMV N6 board or cable.
- Re-established OpenMV IDE connection by connecting the board directly to the laptop USB-A port.
- Investigated persistent blurry camera image.
- Checked OpenMV documentation and confirmed that the lens requires manual focusing.
- Determined that the wrong part of the lens assembly had initially been rotated.
- Adjusted the correct focus ring and improved image sharpness.
- Confirmed that the camera hardware appears to be working correctly.

## 2026-06-15
### Motion Detection Recording Improvements

- Refactored camera code to reduce duplication and improve maintainability.
- Added separate directories for motion videos and still images.
- Generalized file numbering logic to support both video and image files.
- Added configurable recording motion check interval (`_record_motion_check_interval_ms`).
- Refactored motion difference calculation into a dedicated helper function.
- Implemented automatic video file numbering to prevent filename reuse after crashes.
- Added proper MJPEG cleanup using `try/finally` to ensure video files are closed correctly.
- Improved directory creation handling to distinguish between new and existing directories.

### Motion Recording Logic

- Reworked recording behavior to continue recording while motion remains present.
- Replaced continuous per-frame motion checks during recording with configurable interval-based motion verification.
- Implemented periodic motion verification during recording using a configurable timer.
- Confirmed stable operation after resolving MJPEG recording and file corruption issues.
- Successfully tested automatic recording start and stop based on motion activity.

## 2026-06-15
### Camera Configuration Refactor

- Introduced dedicated `MotionConfig` and `StorageConfig` classes.
- Moved motion detection thresholds, timing values, and recording settings out of the Camera class.
- Moved storage paths, filename prefixes, and file extensions into centralized configuration objects.
- Updated Camera to use configuration accessors instead of hardcoded values.
- Improved separation of responsibilities and reduced the number of configuration variables stored directly in the Camera class.

## 2026-06-15
### Camera Code Cleanup

- Added clearer technical comments to the Camera class.
- Documented camera initialization, storage setup, motion detection, recording flow, and frame differencing behavior.
- Removed remaining magic numbers by moving timing and default values into configuration classes.

## 2026-06-15
### RAM Buffer and File Handling Refactor

- Added `BufferConfig` class for RAM circular buffer settings.
- Added configurable buffer duration, buffer FPS, and calculated buffer size.
- Implemented circular RAM frame buffer infrastructure for pre-motion frame storage.
- Added timed frame buffering to store frames at a controlled rate instead of every camera frame.
- Refactored storage naming to shorter `vid` and `img` terminology.
- Refactored duplicated image/video filename construction into reusable `build_filename()` helper.
- Updated image and video counters to use the shared filename builder.
- Verified that RAM buffering works during normal motion monitoring without crashes.
- Confirmed that RAM buffering and MJPEG debug recording work together when frame differencing is excluded from the recording loop.

## 2026-06-16
### Motion Detection Alignment with Updated OpenMV Examples

- Reviewed the latest OpenMV CSI camera examples from the official repository.
- Updated camera initialization to follow the current CSI-based example implementations.
- Updated motion detection logic using guidance from the latest frame differencing examples.
- Updated recording workflow based on the latest MJPEG motion recording examples.
- Investigated the interaction between frame differencing, MJPEG recording, and automatic white balance.
- Verified that motion detection and recording continue to operate correctly after the example-based updates.

## 2026-06-16
### ImageIO Memory Buffer Investigation

- Evaluated OpenMV ImageIO memory streams as a potential implementation for the required RAM-based pre-recording buffer.
- Successfully stored and replayed image frames directly from RAM using ImageIO.
- Observed that repeated ImageIO usage could exhaust fast frame buffer memory.
- Identified that `img.get_histogram()` may trigger `MemoryError: Out of fast frame buffer stack memory` after ImageIO operations if memory is not explicitly released.
- Verified that calling `gc.collect()` immediately after ImageIO stream usage prevents the frame buffer memory exhaustion issue.
- Continued investigating memory management requirements for a long-running circular RAM buffer implementation.

## 2026-06-19
Implemented RAM-based circular pre-buffer recording system.

- Replaced earlier ImageIO buffering experiments with a frame-based circular buffer.
- Added configurable buffer duration and FPS settings through BufferConfig.
- Implemented fixed-size ring buffer storage using modulo indexing.
- Added periodic frame sampling into RAM buffer.
- Added MJPEG export functionality for buffered frames.
- Implemented MJPEG timing patching based on frame count and recorded duration.
- Refactored repeated file patching logic into helper methods.
- Modified motion detection to operate on already captured frames instead of taking additional snapshots.
- Continued cleanup of duplicated configuration values by moving settings into BufferConfig.

Current result:
- Pre-motion video buffering in RAM is operational.
- Buffered video can be saved to storage as MJPEG.
- Playback timing improvements are being tested.
