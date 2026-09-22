# Follow-Me Buggy

A phased, Jetson-powered mobile robotics platform that combines embedded locomotion, custom person detection and tracking, edge vision deployment, and an Android remote-control interface.

[Tanmay Bhatnagar on LinkedIn](https://www.linkedin.com/in/tanmay-bhatnagar/)

This is a documented hardware prototype, not a finished autonomous product. Each phase keeps its own code, setup notes, and limitations close to the implementation.

## What is in the repository

```text
Android app ── Bluetooth Classic (SPP) ──> Jetson Orin Nano ── USB serial ──> Arduino UNO R4 WiFi
    │                                           │                                 │
    └──── HTTP MJPEG / snapshots ───────────────┴──── camera, control, vision ────┴──── motors, servo, ultrasonic
```

| Phase | Focus | Current status |
| --- | --- | --- |
| [Phase 1](phase-1/README.md) | Obstacle-aware four-wheel locomotion | Completed hardware prototype with a serial watchdog, ultrasonic pan scan, and configurable Jetson control policy. |
| [Phase 2](phase-2/README.md) | Custom YOLO follow-me perception | YOLO11n V1 was trained and validated; Jetson/TensorRT and tracker experiments are included. Closed-loop following remains in progress. |
| [Phase 3](phase-3/README.md) | Android remote control and video | Bluetooth SPP D-pad control and a raw MJPEG camera path are implemented. Voice routing and vision-overlay control are not integrated. |

## Technical highlights

- **Embedded control:** Jetson Python state machine communicates with modular Arduino firmware over USB serial; the firmware includes a heartbeat watchdog that stops motors on link loss.
- **Perception:** a custom two-class YOLO11n model (`tanmay`, `other_person`) was trained on a private dataset. The recorded V1 validation set achieved 0.979 mAP50 and 0.805 mAP50-95 across 342 images / 550 instances. These are validation metrics for that dataset, not a claim of real-world autonomous-follow performance.
- **Edge deployment:** Jetson conversion utilities and an experimental [Viam vision-service module](viam-module/jetson-yolo-detector/README.md) package TensorRT YOLO inference for Jetson.
- **Mobile control:** a Kotlin / Jetpack Compose app provides a D-pad, Bluetooth reconnect handling, camera URL/snapshot UI, and a native speech-recognition interface. The Jetson server maps newline-delimited JSON movement messages to Arduino motor commands.
- **Iterative engineering:** the 2025–2026 Git history records hardware bring-up, servo/ultrasonic and serial hardening, custom model development, tracker experiments, Android control, and camera streaming.

## Hardware and software

- NVIDIA Jetson Orin Nano
- Arduino UNO R4 WiFi connected over USB
- HW-130 / L293D motor shield with 74HC595, four geared DC motors, and four-wheel chassis
- HC-SR04 ultrasonic sensor on a pan servo
- USB camera
- Android device for the companion app
- Python on Jetson, Arduino CLI / IDE for firmware, and Android Studio for the mobile app

Phase-specific requirements and commands live in the corresponding phase README. There is intentionally no one-command project setup: motor control, private training data, model artifacts, Jetson software, and Android deployment all require separate, hardware-specific preparation.

## Repository map

```text
phase-1/                 Autonomous locomotion: Arduino firmware + Jetson controller
phase-2/                 Dataset preparation, YOLO training/export, and tracking experiments
phase-3/                 Android app, Bluetooth SPP server, and camera stream server
viam-module/             TensorRT YOLO Viam Vision Service module
testing/                 Hardware bring-up and retained legacy testbench material
utils/                   Optional Mac-to-Jetson SSH/rsync helper
upload_to_arduino.py     Arduino CLI upload and serial-monitor helper
```

Private image data, training outputs, model weights, TensorRT engines, and local device configuration are not committed. To reproduce Phase 2, supply your own data and weights; do not add personal images or credentials to the repository.

## Safety

This repository controls real motors. Start with the wheels elevated, maintain a physical power cut-off, use a correctly rated separate motor supply with a shared ground, and test at low speed in a clear area. Do not treat the ultrasonic sensor or software watchdog as the sole safety mechanism. The Phase 3 camera server is unauthenticated HTTP for a trusted LAN only; do not expose it to public or untrusted networks.

## History and attribution

All project work and commits in this repository are by [Tanmay Bhatnagar](https://github.com/tanmay-bhatnagar). The commit history is retained as an engineering record rather than squashed: it documents the incremental hardware and software decisions behind the current prototype.
