
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

## 2026-06-19
Refactored Camera file-management logic.

- Created VideoFileManager for file-related responsibilities.
- Moved filename generation, directory handling, file numbering, and MJPEG timing patching out of Camera.
- Reduced Camera class responsibilities to camera setup, motion detection, buffering, and recording flow.
- Improved separation between camera logic and storage/file-management logic.

Current status:
Camera.py is cleaner and file-management logic is now isolated in VideoFileManager.

## 2026-06-23
- Refactored pre-buffer recording logic into a dedicated write_prebuffer_with_catchup() helper function.
- Added catch-up frame buffering while pre-buffer frames are being written to the MJPEG file.
- Implemented temporary storage of newly captured frames during the blocking pre-buffer write operation.
- Added playback of catch-up frames immediately after buffered frames to reduce the recording gap between motion detection and live recording.
- Moved video creation logic into a reusable helper function to reduce duplication between recording methods.
- Continued refactoring of Camera class recording functionality into smaller reusable helper methods.
- Verified that catch-up frame buffering works correctly on OpenMV N6 hardware.

## 2026-06-23
- Restored should_check_motion() gating in the main loop to avoid running motion detection on every frame.
- Increased motion detection check interval from 10 ms to 200 ms.
- Reduced CPU load by limiting how frequently histogram-based motion detection is executed.
- Improved overall recording stability while maintaining reliable motion detection with the existing pre-buffer implementation.
- Verified stable operation of 15 FPS recording with a 10-second RAM buffer and catch-up frame buffering enabled.

## 2026-06-23
- Refactored motion detection to use a dedicated low-resolution grayscale analysis frame instead of the full video frame.
- Added create_motion_frame() helper to generate motion-analysis images from the current camera frame.
- Converted motion detection background buffer (_extra_fb) to grayscale and separated it from the video recording pipeline.
- Updated detect_motion() and get_motion_diff() to operate on reduced-resolution grayscale frames.
- Updated background image initialization to use the motion-analysis frame format.
- Restored frame copies in the circular buffer after discovering that storing references prevented preservation of historical frames.
- Investigated memory consumption of VGA buffering and determined that VGA + 15 FPS exceeds available memory when storing independent frame copies.
- Reconfigured buffer settings for stable operation at 640x480 resolution using a 5-second buffer at 5 FPS.
- Verified successful pre-buffer recording and motion-triggered video capture using VGA resolution with the new buffer configuration.

## 2026-06-24
### RAM usage calculations for frame buffering

Calculated estimated RAM usage for storing raw frames in the prebuffer.

RGB565 uses 2 bytes per pixel:

- 160x120 (QQVGA): 38,400 bytes = 37.5 KiB
- 320x240 (QVGA): 153,600 bytes = 150 KiB
- 640x480 (VGA): 614,400 bytes = 600 KiB

Estimated 10-second RGB565 buffer usage:

| Resolution | 5 FPS | 10 FPS | 15 FPS |
|---|---:|---:|---:|
| 160x120 QQVGA | 1.83 MiB | 3.66 MiB | 5.49 MiB |
| 320x240 QVGA | 7.32 MiB | 14.65 MiB | 21.97 MiB |
| 640x480 VGA | 29.30 MiB | 58.59 MiB | 87.89 MiB |

Grayscale uses 1 byte per pixel, so it requires half the RAM of RGB565.

160x120 grayscale:

| FPS | 10-second buffer |
|---:|---:|
| 5 FPS | 0.92 MiB |
| 10 FPS | 1.83 MiB |
| 15 FPS | 2.75 MiB |

Combined motion detection + recording buffer examples:

| Motion detection buffer | Recording buffer | Total |
|---|---:|---:|
| 160x120 grayscale, 5 FPS, 10 s + 320x240 RGB565, 5 FPS, 10 s | 0.92 + 7.32 MiB | 8.24 MiB |
| 160x120 grayscale, 5 FPS, 10 s + 640x480 RGB565, 5 FPS, 10 s | 0.92 + 29.30 MiB | 30.21 MiB |
| 160x120 grayscale, 5 FPS, 10 s + 320x240 RGB565, 10 FPS, 10 s | 0.92 + 14.65 MiB | 15.56 MiB |
| 160x120 grayscale, 5 FPS, 10 s + 640x480 RGB565, 10 FPS, 10 s | 0.92 + 58.59 MiB | 59.51 MiB |

Based on these estimates, VGA RGB565 at 5 FPS for a 10-second prebuffer would require about 29.30 MiB, which should theoretically fit into 64 MiB SDRAM with enough headroom. VGA RGB565 at 10 FPS would require about 58.59 MiB, leaving very little memory for runtime overhead, MicroPython objects, frame buffers, and motion detection.

## 2026-06-25
### Memory usage analysis

- Calculated theoretical RAM requirements for RGB565 and grayscale frame buffers at multiple resolutions and frame rates.
- Measured MicroPython heap usage using `gc.mem_free()` and `gc.mem_alloc()` during camera initialization and buffer allocation.
- Current implementation uses a 5-second VGA RGB565 circular buffer at 5 FPS (25 buffered frames).
- Theoretical RAM usage for the current recording buffer is approximately 14.65 MiB, while the measured MicroPython heap usage increased by approximately 12.2 MiB after the circular buffer was filled.
- Observed that the available MicroPython heap is approximately 24.4 MiB, indicating that the full 64 MiB SDRAM is not exposed as Python heap memory.

## 2026-06-25
### Camera initialization refactoring

- Refactored the `Camera` constructor into clearly separated initialization sections for dependencies, camera setup, hardware indicators, motion detection, and buffer configuration.
- Moved `StorageConfig` and `FileManager` creation outside the `Camera` class and injected them through the constructor to reduce coupling.
- Renamed `VideoFileManager` to `FileManager` to better reflect its broader responsibility for file and directory management.
- Added descriptive memory profiling checkpoints during camera initialization to monitor MicroPython heap usage.

## 2026-06-25
### Corrected PAG7936 memory calculations

- Verified from the OpenMV PAG7936 driver that the sensor uses custom resolution mappings:
  - `csi.QVGA` = 320x200
  - `csi.VGA` = 640x400
  - `csi.HD` = 1280x800
- Updated RGB565 frame buffer RAM calculations to match the actual PAG7936 resolutions.
- Confirmed that the current 5-second `csi.VGA` RGB565 buffer at 5 FPS uses approximately 12.21 MiB, matching measured MicroPython heap usage.

5-second RGB565 buffer:

320x200 @ 5 FPS  =  3.05 MiB
320x200 @ 10 FPS =  6.10 MiB
320x200 @ 15 FPS =  9.16 MiB

640x400 @ 5 FPS  = 12.21 MiB
640x400 @ 10 FPS = 24.41 MiB
640x400 @ 15 FPS = 36.62 MiB

1280x800 @ 5 FPS  =  48.83 MiB
1280x800 @ 10 FPS =  97.66 MiB
1280x800 @ 15 FPS = 146.48 MiB

## 2026-06-25
320x200 @ 5 FPS  =  6.10 MiB
320x200 @ 10 FPS = 12.21 MiB
320x200 @ 15 FPS = 18.31 MiB

640x400 @ 5 FPS  = 24.41 MiB
640x400 @ 10 FPS = 48.83 MiB
640x400 @ 15 FPS = 73.24 MiB

1280x800 @ 5 FPS  =  97.66 MiB
1280x800 @ 10 FPS = 195.31 MiB
1280x800 @ 15 FPS = 292.97 MiB

## 2026-06-25
### PAG7936 buffer resolution limitations

- Investigated the OpenMV PAG7936 firmware driver and confirmed that it supports three native frame buffer resolutions:
  - `csi.QVGA` = 320×200
  - `csi.VGA` = 640×400
  - `csi.HD` = 1280×800
- Verified experimentally that a 5-second RGB565 RAM prebuffer at `csi.HD` (1280×800) exceeds the available MicroPython heap and results in memory exhaustion.
- Confirmed that a 5-second RGB565 RAM prebuffer at `csi.VGA` (640×400) consumes approximately 12.21 MiB and operates reliably.
- Concluded that 640×400 is the highest practical resolution for the current RAM-based circular buffer implementation while maintaining a 5-second prebuffer at 5 FPS.

## 2026-06-25
### FLIR Lepton thermal camera integration

- Integrated the OpenMV Multispectral Thermal Camera Module (FLIR Lepton) into the project.
- Investigated OpenMV's thermal camera examples and documentation, identifying several outdated or incorrect example snippets.
- Determined that the Lepton camera must be initialized using `csi.CSI(cid=csi.LEPTON)` instead of the default CSI constructor.
- Implemented thermal camera initialization, radiometric measurement mode and configurable temperature range.
- Added grayscale-to-temperature conversion for displaying approximate object temperatures.
- Implemented warm target detection based on thermal image statistics.
- Implemented movement detection for warm targets by comparing consecutive thresholded thermal frames.
- Verified successful detection of human body heat and movement using the thermal camera.

### Camera architecture refactoring

- Refactored camera initialization into dedicated methods for the RGB and thermal cameras.
- Added separate initialization and deinitialization functions for the FLIR Lepton camera.
- Prepared the architecture for switching between RGB and thermal cameras without keeping both initialized simultaneously.
- Simplified the `Camera` constructor by grouping related initialization code.
- Updated camera comments and documentation to match the actual PAG7936 VGA resolution (640×400).

### Investigation

- Investigated simultaneous operation of the PAG7936 RGB camera and FLIR Lepton thermal camera.
- Observed that initializing the Lepton camera prevents successful RGB frame capture, suggesting a firmware or CSI driver limitation.
- Began restructuring the camera subsystem to support explicit camera activation and deactivation.

## 2026-07-02
- Recovered the OpenMV N6 firmware by flashing firmware version 4.8.1 using the SingTown VS Code extension.
- Verified that the existing Python camera code works again after restoring a stable firmware version.
- Identified that the crash was firmware-related, not caused by the existing `Camera.py` background image logic.
- Removed the unstable custom MJPEG firmware changes from the active test path.

## 2026-07-02
- Confirmed that mixed-resolution MJPEG recording works directly in Python.
- Validated the intended recording pipeline: VGA RAM prebuffer frames can be written first, then the camera can switch to HD for live recording in the same MJPEG file.

## 2026-07-02
- Investigated the architecture required for simultaneous RGB and thermal camera operation.
- Determined from OpenMV developer guidance that true parallel RGB and thermal capture is not possible on a single OpenMV N6. It requires separate processors (for example, two OpenMV boards communicating over a serial protocol with optional FSIN/VSYNC synchronization).

## 2026-07-06
Firmware migration to OpenMV 5.0.0

Updated the project from OpenMV firmware 4.8.1 to OpenMV 5.0.0 and successfully debugged the PAG7936 camera to work with the new firmware. The migration required investigating changes in the camera API and updating the camera initialization code accordingly.

The PAG7936 camera is now fully operational on firmware 5.0.0, restoring image capture functionality and allowing the project to continue on the latest firmware version. During the migration, the Camera.py implementation was updated to match the new firmware behavior, including adapting to API changes introduced in OpenMV 5.0.0.

A clean copy of the OpenMV 4.8.1 source code was also downloaded for future source-level comparisons between firmware versions when debugging regressions or behavior changes.

## 2026-07-06
Continued debugging the OpenMV 5.0.0 firmware migration and identified that initializing the Lepton thermal camera causes subsequent PAG7936 frame captures to fail with `RuntimeError: Frame capture has timed out`. Determined that reinitializing the PAG7936 camera after the Lepton initialization restores normal operation, indicating that the Lepton initialization changes the CSI camera state in firmware 5.0.0. This narrows the remaining work to debugging the CSI initialization sequence rather than the application logic.

## 2026-07-06
Restored the Lepton thermal camera functionality on OpenMV firmware 5.0.0. Found that the thermal preview does not appear in OpenMV IDE unless the captured frame is explicitly flushed with `flush()`. Updated the thermal camera flow so the latest Lepton frame is captured, flushed to the IDE preview, stored as the current frame, and then used for warm-target movement detection.

## 2026-07-06
Investigated simultaneous use of the PAG7936 RGB camera and Lepton thermal camera on OpenMV 5.0.0. Testing and firmware debugging indicate that both cameras cannot operate as independent continuous streams on a single OpenMV N6. Initializing the Lepton changes the CSI state, requiring the PAG7936 camera to be reinitialized before it can capture frames again. This indicates that the project should switch between thermal monitoring and RGB recording modes instead of attempting to stream both cameras simultaneously.

## 2026-07-06
Camera pipeline improvements

- Implemented automatic switching between the Lepton thermal camera and the PAG7936 RGB camera.
- Lepton now continuously captures thermal frames, updates the thermal frame buffer, and performs warm target movement detection.
- When movement is detected, the system automatically switches to the PAG7936 camera, records RGB video, and monitors motion until it stops.
- After recording ends, the system automatically reinitializes the Lepton camera and resumes thermal monitoring.
- Resolved multiple OpenMV 5.0.0 camera switching issues, including camera reinitialization, framebuffer initialization, and reliable RGB motion-stop detection after switching from the thermal camera.

## 2026-07-07
Camera.py documentation and refactoring

- Added descriptive comments above all major functions to improve readability and maintainability.
- Refactored Camera.py to improve function organization and code clarity without changing functionality.
- Documented the responsibilities of the RGB camera, Lepton thermal camera, circular frame buffer, and recording pipeline.
- Clarified the dual-camera workflow by documenting camera switching, motion detection, recording, and cleanup functions.
- Standardized function documentation using concise comments above each function, following the project's C/C++ documentation style.


## 2026-07-07
Recording workflow improvements

- Simplified the recording workflow by removing the separate recording-time motion detection implementation.
- Reused the existing adaptive background frame differencing algorithm for motion detection during RGB recording.
- Fixed the recording loop so it correctly stops once motion is no longer detected.
- Refactored the recording pipeline to use a single motion detection implementation for both monitoring and recording.


## 2026-07-08
MJPEG AVI index patching

- Implemented AVI idx1 index patching for OpenMV-generated MJPEG files.
- Added automatic scanning of MJPEG frame chunks and generation of the missing AVI index.
- Updated the RIFF container size after appending the idx1 chunk.
- Fixed MJPEG playback so media players immediately recognize the correct video duration and support proper seeking without rebuilding the AVI index.


## 2026-07-08
NetworkManager foundation

- Added the initial NetworkManager class to separate networking functionality from the camera logic.
- Designed the networking architecture to support both the current WiFi implementation and a future mobile communication module.
- Added NetworkConfig to isolate network credentials from the networking implementation.
- Updated .gitignore to exclude the local NetworkConfig file from version control while allowing an example configuration to be shared with the project.


## 2026-07-08
Network connection and time synchronization

- Added NetworkManager initialization for setting up the network connection from main.py.
- Added NTP-based time synchronization so the OpenMV RTC can be updated after network connection.


## 2026-07-14
AWS cloud upload implementation

- Created an AWS S3 bucket for storing recorded MJPEG files.
- Created an AWS Lambda function that generates temporary presigned S3 upload URLs.
- Configured the Lambda execution role with restricted S3 PutObject permission.
- Created an API Gateway HTTPS endpoint for requesting presigned upload URLs.
- Implemented MJPEG uploading in NetworkManager using a TLS socket.
- Streamed MJPEG files to S3 in 4 KiB chunks without loading the complete recording into RAM.
- Verified a successful end-to-end upload of a 24.6 MB MJPEG recording from the OpenMV N6 to Amazon S3.
- Confirmed that S3 returned HTTP 200 OK and that the uploaded video remained playable.


## 2026-07-14
AWS upload performance optimization

- Benchmarked MJPEG upload performance using 4 KiB, 8 KiB, 16 KiB and 32 KiB socket streaming chunk sizes with the same recording.
- Verified successful uploads and HTTP 200 OK responses from Amazon S3 with all tested chunk sizes.
- Selected a 16 KiB upload chunk size as the current default because it provided the best overall performance while maintaining stable operation.
- The selected chunk size will be validated again under the final runtime conditions where motion detection and the frame buffer remain active during uploads.
- The planned upload workflow is to automatically upload all MJPEG recordings found in the motion_capture directory whenever the camera is idle. If new motion is detected, the current upload will be interrupted immediately, recording will resume, and the remaining files will continue uploading once the camera becomes idle again.


## 2026-07-15
### Devlog

* Added configurable MJPEG upload scheduling.
* Implemented upload modes:

  * Instantly
  * Hourly
  * Twice per day
  * Once per day
* Added configurable upload times for scheduled uploads.
* Implemented a lightweight scheduler that checks upload conditions once per minute using `time.ticks_ms()`.
* Created `UploadConfig` to centralize upload scheduling configuration.
* Refactored upload configuration to use a single settings structure as the source of truth, simplifying configuration management.
* Integrated scheduled upload functionality into `NetworkManager`.


## 2026-07-15
Implemented an AWS S3 event-driven processing pipeline for uploaded MJPEG videos.

- Configured an S3 event notification to automatically invoke the ProcessUploadedMJPEG Lambda function whenever a new MJPEG file is uploaded.
- Implemented Lambda functionality to download uploaded MJPEG files directly from S3 to temporary storage.
- Developed an MJPEG parser that detects individual JPEG frame boundaries using JPEG start (FFD8) and end (FFD9) markers.
- Verified the parser by counting the total number of frames contained in uploaded MJPEG files.
- Extended the Lambda implementation to extract every JPEG frame from the MJPEG stream.
- Optimized frame extraction to upload each JPEG frame directly to S3 from memory without storing all extracted frames simultaneously on disk.
- Added automatic creation of per-video frame directories under the frames/ folder in S3.
- Verified the complete processing pipeline by successfully extracting and uploading all JPEG frames from uploaded MJPEG recordings.

## 2026-07-16
- Investigated upload-time resets occurring after RGB video recording and during HTTPS uploads.
- Added memory diagnostics before upload, after TLS initialization and before file streaming to identify the failure point.
- Added upload progress logging to monitor long MJPEG transfers.
- Determined that the resets occurred after the PAG7936 camera had been used rather than during MJPEG file streaming.
- Shut down the PAG7936 camera before starting HTTPS uploads to release camera resources.
- Verified stable MJPEG uploads after the camera shutdown change.
- Confirmed that the original 16384-byte upload buffer operates reliably after shutting down the PAG7936 camera, making the previous chunk-size reduction unnecessary.

## 2026-07-16
- Completed the AWS serverless processing pipeline for uploaded MJPEG videos.
- Configured Amazon S3 to automatically trigger an AWS Lambda function when a new MJPEG video is uploaded.
- Implemented automatic MJPEG frame extraction and uploaded all extracted JPEG frames to S3.
- Integrated Amazon Rekognition to analyze selected video frames for object detection.
- Generated a JSON results file containing frame metadata, detected labels, confidence values and bounding boxes.
- Added a video-level detection summary that confirms repeated detections across multiple analyzed frames to reduce false positives.
- Verified the complete end-to-end workflow from OpenMV upload to automatic AI analysis and JSON result generation in AWS.

## 2026-07-16
AWS Repository Improvements

- Added the final AWS Lambda source code (`upload_handler.py`) to the repository to keep the cloud implementation under version control.
- Added the default `upload_settings.json` configuration file to the repository for version-controlled AI processing settings and target species configuration.
- Expanded the default target species configuration to include common Finnish wildlife together with generic animal and human detection labels.
- Verified that the repository configuration matches the deployed AWS Lambda implementation.

## 2026-07-16
AWS Processing Metadata Storage

- Added DynamoDB integration to store processing metadata for every uploaded MJPEG video.
- Implemented automatic metadata writes from the AWS Lambda processing pipeline after successful video analysis.
- Stored processing status, source video information, frame statistics, processing duration and S3 object locations in DynamoDB.
- Added detection summary and target-species detection results to each processing record.
- Chose DynamoDB because it provides fast key-based lookups, scales automatically, requires no server management and is well suited for tracking the processing state of individual uploaded videos.
- Verified successful end-to-end integration between AWS Lambda and DynamoDB by confirming that processed videos automatically create metadata records.


## 2026-07-21
Thermal Blob Detection

* Replaced the previous binary frame-difference based thermal detection with blob-based thermal target detection.
* Added a warm-region check that verifies the hottest area is significantly warmer than the average scene temperature before blob detection.
* Added configurable blob size thresholds to filter small thermal noise and reject excessively large warm background regions.
* Refactored the thermal detection logic into separate warm region and blob detection functions to improve readability and maintainability.
* Documented all thermal detection thresholds with comments explaining the grayscale-to-temperature mapping and blob filtering parameters.


## 2026-07-21
Recording Motion Detection Improvements

* Replaced the RGB recording motion detection with blob-based frame differencing using find_blobs().
* Added configurable blob size thresholds to filter out small noise and large scene-wide changes.
* Added a configurable no-motion timeout to keep recording while wildlife temporarily stops moving.
* Added a maximum recording duration to prevent recordings from continuing indefinitely.
* Simplified the recording logic and updated comments to match the new motion detection workflow.


## 2026-07-21
Removing Obsolete Code

- Removed unused camera state variables left over from the previous motion detection implementation.
- Removed obsolete thermal frame-difference variables that are no longer required by the blob-based thermal detector.
- Removed unused adaptive background detection configuration values and their associated getter functions.
- Removed obsolete timing, stabilization, debugging, and file counter configuration values from MotionConfig.
- Removed unused imports from Camera and NetworkManager.
- Simplified the codebase by removing legacy code that is no longer used by the current motion detection and recording pipeline.


## 2026-07-22
Improved thermal wildlife detection range

- Tuned the thermal detection parameters for significantly longer detection range.
- Reduced the minimum thermal contrast threshold from 6°C to 2°C while maintaining stable operation.
- Experimented with multiple thermal grayscale thresholds to evaluate detection distance.
- Determined that a thermal threshold of (50, 255) provides the best balance between detection range and false positives.
- Verified reliable human detection from approximately 10 meters, even while wearing a hoodie.
- Added blob debugging output to inspect detected thermal target size during field testing.
- Confirmed that distant targets can be detected as small as a 2×2 pixel thermal blob, allowing very small warm targets to trigger recording.

## 2026-07-29
Fix RGB motion detection first-frame logic

- Fixed a logic bug in RGB motion detection where the first frame of a recording incorrectly returned a movement detection.
- Changed the first-frame handling to return False because no previous frame exists for comparison.
- Clarified the comments to distinguish initialization from actual movement detection.
- Prevented the recording logic from refreshing the last-motion timestamp before a valid frame comparison is possible.


## 2026-07-29
Dual-camera thermal motion detection

- Enabled simultaneous PAG7936 and Lepton operation using a soft Lepton reset (`hard=False`).
- Kept PAG7936 capturing RGB frames into the circular frame buffer while using the Lepton exclusively for thermal motion detection.
- Switched thermal detection to native 160×120 frame differencing with an adaptive background image.
- Replaced the previous thermal detection algorithm with histogram percentile-based frame differencing for more reliable movement detection.
- Configured thermal motion detection to run at 5 Hz and tuned the background update interval for faster recovery after movement.


## 2026-07-30
Corrected MJPEG recording resolution

- Added explicit 1280×800 dimensions when initializing the MJPEG file.
- Fixed MJPEG initialization so live recording now starts directly at 1280×800 resolution.
- Added a reusable 1280×800 RGB565 frame for scaling buffered frames without repeated large memory allocations.
- Scaled all buffered and catch-up frames to 1280×800 before writing them to the MJPEG file.
- Verified that the generated MJPEG videos contain 1280×800 frames and preserve the correct playback duration.

## 2026-08-03
Codebase cleanup and encapsulation

- Removed obsolete variables, configuration values, helper functions, and unused file-management features.
- Removed the old RGB motion-detection and thermal blob-detection code left behind after switching to thermal frame differencing.
- Removed unused still-image, temporary-directory, and standalone prebuffer-saving functionality.
- Simplified the remaining configuration classes to contain only values used by the current runtime pipeline.
- Marked class-internal methods as private by adding leading underscores.
- Updated internal method calls to match the new private method names.
- Reduced the codebase to the functionality currently required for buffering, thermal motion detection, MJPEG recording, and AWS uploads.


## 2026-08-03
Reorganized camera initialization and corrected comments

- Reorganized the Camera class initialization into clearer sections for dependencies, configuration, recording state, buffering, thermal detection, and camera setup.
- Kept both CSI camera objects initialized directly inside __init__ to preserve the working MicroPython initialization behavior.
- Corrected PAG7936 resolution comments from 640×480 to the actual 640×400 output.
- Updated comments to correctly distinguish RGB prebuffer frames from thermal detection frames.
- Clarified the purpose of the Lepton soft reset, stabilization period, background frame, and reusable scaling buffer.
- Removed the unnecessary thermal detection state variable and returned the trigger result directly.


## 2026-08-03
Converted the runtime pipeline to non-blocking asyncio tasks

- Replaced the sequential main loop with concurrent asyncio tasks for RGB prebuffer capture, thermal motion detection, and AWS uploads.
- Converted the S3 upload pipeline to asynchronous TCP/TLS streams using asyncio.open_connection(), writer.write(), and await writer.drain().
- Kept MJPEG recording intentionally blocking so the recording pipeline has exclusive control of the cameras.
- Added a startup delay before the upload task so both camera interfaces and the circular prebuffer can stabilize.
- Verified that large MJPEG files can be uploaded while both camera tasks continue running.
- Fixed upload stability by removing gc.collect() from the circular-buffer wrap, as garbage collection during active TLS transfers caused embedded-system crashes.
- Confirmed stable memory usage during repeated circular-buffer cycles and consecutive asynchronous uploads.
- Updated AWS processing to route S3 events through SQS with a batch size of one, ensuring each video receives its own Lambda invocation and processing timeout.
- Verified successful S3 uploads, HTTP 200 responses, local file deletion after confirmation, and continued camera operation during transfer.


## 2026-08-04
Improve AWS Lambda documentation and readability

- Improved function-level comments throughout the AWS Lambda processing pipeline.
- Added clearer explanations for MJPEG frame extraction, Rekognition analysis, detection summaries, and S3 processing.
- Added higher-level comments describing the processing stages and data flow.
- Improved code readability and maintainability without changing the existing functionality.


## 2026-08-10
Rebuilt AWS upload backend and continued embedded stability improvements

- Rebuilt the AWS upload backend from the ground up using S3, Lambda, API Gateway, IAM permissions, and presigned upload URLs.
- Moved the S3 bucket name and upload prefix to Lambda environment variables instead of hardcoding deployment-specific configuration.
- Created the `/upload-url` API endpoint for requesting temporary presigned S3 upload URLs.
- Successfully tested the complete OpenMV → API Gateway → Lambda → S3 upload pipeline with multiple MJPEG files.
- Removed the unnecessary processing status endpoint because the embedded device only needs to determine whether the S3 upload succeeded.
- Updated the example network configuration for the new AWS API endpoint.
- Enabled `auto_gain`, `auto_exposure`, and `auto_rotation` for the RGB camera.
- Continued stress testing simultaneous frame buffering, motion-triggered recording, SD card access, networking, TLS, and S3 uploads.
- Changed motion monitoring so the intentionally blocking `record_video()` operation runs directly from the async motion task instead of being wrapped as an asynchronous recording operation.
- Investigated intermittent hard crashes during concurrent camera and network operation using additional memory, TLS, upload, and recording debug markers.
- Tested MicroPython automatic garbage collection and removed forced garbage collection from memory-status reporting for stability testing.
- Confirmed that automatic garbage collection can reclaim substantial heap memory without explicit `gc.collect()` calls.
- Tested both `requests.post()` and direct asynchronous HTTPS for requesting presigned URLs; hard crashes occurred with both approaches, so `requests` was restored and ruled out as the sole cause.
- Prepared a dedicated `Watchdog` class for later integration and identified the blocking recording loop as an additional location where the watchdog will need to be fed.
- Added the `/sdcard/logs` directory in preparation for persistent boot, storage, power, and crash-state logging.

## 2026-08-11
Stabilized concurrent camera recording and asynchronous S3 uploads

- Converted the S3 upload path to asynchronous networking so uploads can run concurrently with the camera task.
- Added asynchronous HTTPS handling for requesting presigned S3 upload URLs and transferring MJPEG files.
- Added error handling and cleanup around network streams and upload operations.
- Isolated the hard-reset issue to memory pressure during concurrent camera and network workloads.
- Added explicit garbage collection before and after MJPEG uploads and video recordings.
- Verified that manual memory cleanup consistently restores available heap during continuous camera and upload operation.
- Successfully uploaded multiple large MJPEG files while the camera prebuffer continued running.
- Verified that video recording can run during an active upload without causing a system reset.
- Confirmed that long blocking recordings can still cause the active TLS connection to return ECONNRESET, while the application continues running and recovers afterward.

## 2026-08-12
Added Lepton frame buffering, thermal MJPEG recording, and shared camera logic

- Added a dedicated circular frame buffer for the FLIR Lepton thermal camera alongside the existing PAG7936 RGB buffer.
- Added asynchronous Lepton frame-buffer updates so RGB and thermal prebuffers run concurrently.
- Refactored several camera functions to be reusable for both PAG7936 and Lepton instead of maintaining separate duplicated implementations.
- Generalized `_save_frame()` so both cameras use the same circular-buffer storage logic with separate buffers, indexes, and fill counters.
- Generalized `get_ordered_buf_frames()` and `clear_frame_buffer()` so the same logic can operate on either camera buffer.
- Generalized `create_motion_video()` so recording resolution and filename prefix can be passed per camera.
- Refactored the PAG7936 and Lepton recording resolutions into variables instead of using hard-coded magic numbers.
- Added simultaneous PAG7936 and Lepton MJPEG recording for motion-triggered events.
- Added separate recording files and filename prefixes for RGB and thermal videos.
- Extended prebuffer and catch-up handling so both RGB and thermal frames are written before live recording begins.
- Added fresh Lepton snapshots during catch-up recording instead of reusing the same thermal frame.
- Added separate frame counters and MJPEG timing/index patching for RGB and thermal recordings.
- Updated recording-state cleanup to clear both RGB and thermal circular buffers after an event.

## 2026-08-12
Removed remaining magic numbers and centralized configuration

- Added CameraConfig to centralize camera-specific configuration values.
- Replaced hard-coded camera resolutions, stabilization delays, and recording limits with configuration values.
- Moved motion detection thresholds, temperature ranges, histogram percentiles, and background update values into MotionConfig.
- Moved network timing, retry, TLS, upload chunk size, and progress reporting values into UploadConfig.
- Updated the code to use the new configuration values instead of hard-coded values.
- Updated dual-camera file counter initialization to prevent filename conflicts between PAG7936 and Lepton recordings.

## 2026-08-13
Added storage quotas, rotating logs, and Finland-local timestamps

- Added logical SD-card quotas to separate video storage from log storage while keeping a safety reserve.
- Added video storage checks so new recordings are rejected when the reserved video area is full.
- Added LogManager with sequential log files, configurable file rotation, and automatic deletion of the oldest logs when the log quota is exceeded.
- Added reusable INFO, WARNING, and ERROR logging methods.
- Added filesystem capacity and directory usage calculations for storage management.
- Added TimeManager for Finnish winter/summer time handling.
- Updated NTP synchronization so the RTC is converted from UTC to Finnish local time, giving log entries and SD-card files correct local timestamps.

## 2026-08-13
Storage Quotas, Persistent Logging and Watchdog Integration

- Separated SD card storage into reserved video and log quotas to prevent either data type from consuming the entire storage capacity.
- Added automatic deletion of the oldest log files when the reserved log storage becomes full.
- Prevented new video recordings from starting when the reserved video storage quota is reached.
- Added persistent timestamped logging for system boot events, video recording events, storage conditions and network operations.
- Added Finnish local-time handling, including daylight-saving time, so filesystem and log timestamps use the correct local time.
- Added hardware watchdog support with periodic feeding during normal asynchronous operation and blocking video recording.
- Added watchdog reset-cause logging to identify watchdog-triggered system restarts.
- Added periodic garbage collection when the PAG7936 circular frame buffer wraps to reduce memory pressure during concurrent buffering and uploads.
- Added camera ID, event ID and sensor metadata to MJPEG upload requests in preparation for organizing paired PAG7936 and Lepton recordings on AWS.
- Estimated SD card recording capacity based on real 60-second recordings: approximately 410 complete dual-camera events (~820 MJPEG files) on 29.6 GB of storage. A full 60-second event uses approximately 74 MB for the PAG7936 recording and 1.2 MB for the Lepton recording (~75 MB combined).

## 2026-08-14
Improved long-term system stability

- Added periodic garbage collection inside the video recording loop to reclaim temporary allocations during recording.
- Resolved the memory-related instability that caused the embedded system to crash during extended operation.
- Verified over 8 hours of uninterrupted operation with repeated dual-camera recordings and the hardware watchdog enabled.
- Re-enabled the network upload task and verified over 3 hours of uninterrupted operation with recording, buffering, watchdog and uploads active.
- Confirmed the system remained operational until the test was manually stopped.

## 2026-08-15
## Improved Thermal Detection and Fixed MJPEG Timing

- Investigated FLIR Lepton temperature ranges for improving thermal frame differencing.
- Added maximum-temperature measurement for testing the actual temperatures detected by the FLIR Lepton at different distances.
- Verified that the PAG7936 5-second RAM circular pre-buffer correctly contains all 25 expected frames when an event is triggered.
- Diagnosed an MJPEG playback issue and found an incorrect AVI stream length calculation in the custom header patching logic.
- Fixed the AVI stream length to use the actual number of recorded frames.
- Verified that the corrected MJPEG frame count, 5 FPS frame rate and playback duration now match correctly.

## 2026-08-16
- Investigated the FLIR Lepton 3.5 Flat-Field Correction (FFC) behavior after periodic calibration events were found to interfere with thermal frame-difference motion detection.
- Implemented FFC status monitoring based on an OpenMV developer example using `IOCTL_LEPTON_GET_ATTRIBUTE` with the Lepton FFC status attribute (`0x0244`): https://forums.openmv.io/t/flir-lepton-3-5-shutter/1356
- Added logic to suspend thermal frame-difference motion detection during FFC and for a 5-second stabilization period afterwards.
- Replaced the thermal background reference after FFC recovery so that post-calibration frames are not compared against a pre-calibration background.
- Reduced FFC status polling to once per second to minimize unnecessary Lepton `ioctl` calls.

## 2026-08-16
a 2-second post-FFC recovery proved insufficient, so the recovery period was increased to 5 seconds, which eliminated the immediate post-FFC false triggers in testing.

## 2026-08-18
### Garbage Collection Improvements

- Configured MicroPython garbage collection with a 10 MB allocation threshold.
- Removed manual garbage collection calls from the `Camera` class.
- Automatic garbage collection now handles memory cleanup instead of manually triggering collection in memory-heavy camera operations.
- Completed an overnight stress test lasting approximately 11 hours without crashes or memory-related failures.
- The system continued camera processing, ring-buffer operation, FFC handling, and video recording successfully throughout the test.
- `upload_task` was disabled during this stress test to isolate and validate the camera and memory-management pipeline.

## 2026-08-18
### Camera Architecture Refactoring

- Refactored the original monolithic `Camera` class into separate camera-specific classes.
- Added `CameraBase` for shared camera functionality and configuration.
- Added `CameraPag` for PAG7936-specific initialization, RGB buffering, frame scaling, and prebuffer handling.
- Added `CameraLepton` for FLIR Lepton initialization, thermal buffering, motion detection, and FFC handling.
- Added `CameraManager` to coordinate both camera instances and manage shared camera-system operations.
- Moved common frame-buffer helper methods into `CameraBase` so they can be reused through inheritance.
- Changed PAG7936 and Lepton frame-buffer loops to run concurrently through the camera manager.
- Added safe handling for temporarily unavailable Lepton frames during motion detection.
- Verified the refactored camera architecture with successful motion detection and MJPEG recording.
- Verified PAG7936 live recording at approximately 4.84 FPS against the 5 FPS target.

## 2026-08-18
### Recording State Machine Refactoring

- Replaced the previous recording workflow with a state machine managed by `CameraManager`.
- Added `PREPARE`, `PREBUFFER`, `RECORDING`, and `FINALIZING` recording states.
- Split the recording lifecycle into dedicated state methods for file preparation, prebuffer writing, live recording, and finalization.
- Kept the recording state machine synchronous while asynchronous tasks continue to handle frame buffering and motion monitoring.
- Integrated both PAG7936 and Lepton recording operations into the shared state-machine flow.
- Standardized camera buffer attributes to use the shared implementation inherited from `CameraBase`.
- Added exception handling around the state machine and ensured the recording state always resets to `PREPARE`.
- Removed unused imports and redundant configuration dependencies after the refactoring.

## 2026-08-18
### Camera Recording Logic Cleanup

- Continued refactoring the recording architecture to reduce camera-specific logic inside `CameraManager`.
- Added camera-specific `record_frame()` methods to `CameraPag` and `CameraLepton`.
- Moved PAG7936 recording-mode resolution switching into `CameraPag`.
- Moved MJPEG video preparation and finalization into the individual camera classes.
- Moved the shared MJPEG creation logic into `CameraBase` for reuse through inheritance.
- Updated `CameraBase` to handle circular-buffer clearing and internal buffer-state reset.
- Simplified `CameraManager` so it primarily coordinates recording states and calls camera-specific operations.
- Removed redundant video closing, duration calculations, and unused imports from `CameraManager`.

## 2026-08-20
### Upload Stability Fix

- Investigated repeated watchdog resets during S3 uploads.
- Isolated the failure to the file-streaming phase.
- Added WLAN connection checks between file uploads.
- Added exception handling around the upload streaming loop.
- Added exception handling to `write_log()` so logging failures are reported and re-raised.
- Added post-upload memory cleanup for both successful and failed uploads.
- Added a timeout to `writer.drain()` so stalled uploads are aborted before triggering a watchdog reset.
- Failed uploads now keep the original file and allow the system to continue operating.
- Verified recovery from a stalled PAG upload during stress testing.
- Completed an almost three-hour stress test without an unintended reset.

