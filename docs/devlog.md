
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
