
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

### Next Steps

* Learn OpenMV N6 camera functionality and continuous frame capture workflow.
* Investigate motion detection methods supported by OpenMV N6.
* Design a rolling RAM buffer that continuously stores approximately the latest 10 seconds of captured frames.
* Implement motion-triggered recording where saved footage includes the 10 seconds captured before the motion event.
* Continue recording for as long as motion is detected.
* Add an inactivity timeout so recording stops only after motion has ended.
* Evaluate memory usage, frame rate, resolution, and compression options for the 10-second pre-event buffer.

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

### Next Steps

- Continue implementing motion-triggered MJPEG recording.
- Build the first version where motion detection starts video recording.

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

### Next Steps

- Implement frame differencing based motion detection.
- Create a rolling RAM buffer for approximately 10 seconds of pre-event footage.
- Trigger MJPEG recording automatically when motion is detected.
- Save buffered frames preceding the motion event before continuing live recording.

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

### Next Steps

- Implement a 10-second circular RAM buffer for video frames.
- Store pre-motion frames in memory before motion is detected.
- Begin automatic recording when motion is detected while preserving the buffered footage.
- Continue development and testing on Monday.
