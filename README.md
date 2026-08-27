# Smart Wildlife Monitoring System

> A smart dual-camera wildlife monitoring system built with the OpenMV N6 that automatically detects, records, uploads, and identifies wildlife using thermal imaging, computer vision, and AWS cloud services.

![IoT Wildlife Camera](images/IoT-Project-Asyncio.png)

---

## Overview

This project is a fully autonomous wildlife camera designed to monitor nature without human intervention.

The system continuously monitors the environment using a FLIR Lepton thermal camera while maintaining circular RGB and thermal frame buffers in memory. When thermal motion is detected, the buffered frames are preserved and both PAG7936 RGB and FLIR Lepton recordings are stored as MJPEG files. The recordings are then uploaded to AWS for automatic wildlife recognition.

The embedded software is written entirely in **MicroPython** for the **OpenMV N6**. The runtime uses **MicroPython's asyncio**, allowing cloud uploads to execute in the background while camera monitoring continues.

---

## Demo

🎥 **Outdoor Test – PAG7936 RGB & FLIR Lepton**

Outdoor test footage demonstrating the PAG7936 RGB camera and FLIR Lepton thermal camera in the OpenMV N6 wildlife camera system.

▶️ [Watch the test video on YouTube](https://www.youtube.com/watch?v=YeA9baXi2Uw)

---

## Features

- 🔥 Thermal motion detection using a FLIR Lepton camera
- 📷 High-quality RGB recording using the PAG7936 camera
- 🧠 5-second circular RGB and thermal frame buffers
- 🎥 Automatic PAG7936 and Lepton MJPEG event recording
- ⚡ Asynchronous runtime powered by MicroPython `asyncio`
- ☁️ Background uploads to Amazon S3
- 🤖 Automatic wildlife recognition using Amazon Rekognition
- 💾 Automatic local storage on microSD
- 🛡️ Hardware watchdog and automatic fault recovery
- 🌡️ FLIR Lepton Flat-Field Correction (FFC) handling

---

## System Architecture

```text
             FLIR Lepton
                   │
                   ▼
        Thermal Motion Detection
                   │
          Motion Detected?
             No │      Yes
                │
                ▼
      RGB Circular Frame Buffer
                │
                ▼
       MJPEG Video Recording
                │
                ▼
  Async Background Upload (S3)
                │
                ▼
            AWS Lambda
                │
                ▼
      Amazon Rekognition
                │
                ▼
       Target-Specific S3 Folders
```

---

## Hardware

| Component | Description |
|-----------|-------------|
| OpenMV N6 | Main embedded platform |
| PAG7936 | RGB camera |
| FLIR Lepton | Thermal camera |
| microSD | Local video storage |

---

## Software Stack

### Embedded

- MicroPython
- OpenMV Firmware
- MicroPython `asyncio`

### AWS

- Amazon API Gateway
- AWS Lambda
- Amazon S3
- Amazon Rekognition

---

## How It Works

1. The FLIR Lepton continuously monitors the environment for thermal motion.
2. Both cameras continuously maintain 5-second circular pre-event buffers.
3. Thermal motion triggers an event.
4. Buffered PAG7936 and Lepton frames are preserved.
5. Both cameras continue recording the event as MJPEG files.
6. The recordings are stored locally on the microSD card.
7. The files are uploaded asynchronously to Amazon S3 using presigned upload URLs.
8. S3 ObjectCreated events invoke AWS Lambda.
9. Lambda extracts selected frames from the PAG7936 MJPEG recording.
10. Amazon Rekognition analyzes the frames for configured targets.
11. Detected target frames are stored in target-specific S3 folders.
12. Events without configured targets can be rejected and removed.

---

## Current Status

| Feature | Status |
|----------|--------|
| Dual-camera operation | ✅ Complete |
| Thermal motion detection | ✅ Complete |
| RGB and thermal circular prebuffers | ✅ Complete |
| PAG7936 and Lepton MJPEG recording | ✅ Complete |
| FFC handling | ✅ Complete |
| Hardware watchdog recovery | ✅ Complete |
| Asynchronous cloud uploads | ✅ Complete |
| AWS processing pipeline | ✅ Complete |
| Amazon Rekognition integration | ✅ Complete |

---

## Repository Structure

```text
.
├── aws/                 AWS Lambda functions and cloud configuration
├── docs/                Development log and project documentation
├── firmware/            OpenMV N6 MicroPython firmware
├── add_devlog.py        Script for adding development log entries
├── deploy.bat           Deployment script
├── .gitignore
└── README.md
```

---

## Acknowledgements

This project was developed as part of my Embedded Software Engineering studies at Metropolia University of Applied Sciences while exploring embedded systems, computer vision, thermal imaging, asynchronous programming, and cloud-connected IoT systems.
