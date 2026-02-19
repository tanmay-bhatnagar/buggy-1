# Phase 3: Bluetooth Companion App (Android)

Bluetooth-connected Android app for long-range navigation, voice commands, and RC control of the follow-me buggy.

---

## ⚠️ Current Status

| Component | Status |
|-----------|--------|
| **BLE/Classic BT Link** | ⏳ Pending |
| **Long-Range Navigation (3.1)** | ⏳ Pending |
| **Voice Commands (3.2)** | ⏳ Pending |
| **RC Mode + Livestream (3.3)** | ⏳ Pending |

---

## Overview

| Component | Details |
|-----------|---------|
| **Platform** | Android (Kotlin / Jetpack Compose) |
| **Connectivity** | Bluetooth Classic (SPP - Full Force) |
| **Target Device** | Jetson Orin Nano (via External Dongle) |
| **Backdoor** | Arduino UNO R4 (ESP32-S3) as secondary gateway |
| **Camera Feed** | MJPEG Stream via Jetson |

---

## Feature Modules

### 3.1 Long-Range Navigation (Bluetooth Beacon)
When the buggy **cannot see you** (YOLO detection lost), the Bluetooth signal guides it back:
- **RSSI-based directionality**: use signal strength to approximate heading
- **Obstacle avoidance**: Phase-1 ultrasonic still active during BT-guided approach
- **Handoff**: once close enough for YOLO detection → seamlessly switch to visual follow mode
- **Fallback**: if BT signal degrades, buggy holds position and waits

### 3.2 Voice Commands (Over Bluetooth)
High-fidelity BT link enables real-time voice control:
- **STT on phone**: speech-to-text processing on Android to save Jetson compute
- **Command vocabulary**: "stop", "come here", "follow me", "go home", "faster", "slower", etc.
- **Feedback**: buggy acknowledges via on-screen status or audio cue
- **Intent parsing**: lightweight NLP or keyword matching on phone before sending command over BT

### 3.3 RC Mode + Camera Livestream
Full remote control with FPV-style camera view:
- **Dual-stick virtual joystick**: left stick = fwd/back, right stick = steering
- **Tilt-to-steer option**: accelerometer-based steering
- **Camera livestream**: low-latency video from buggy's camera displayed on phone
- **Mode toggle**: switch between autonomous follow-me and manual RC control
- **HUD overlay**: speed, battery, distance, connection quality indicators

---

## Architecture (High-Level)

```
┌─────────────┐        Bluetooth         ┌──────────────────────┐
│  Android     │  ◄──── Classic/BLE ────► │  Jetson Orin Nano    │
│  Phone App   │                          │                      │
│              │  Commands (JSON/Proto)   │  ┌──────────────┐    │
│  STT Engine  │  ─────────────────────►  │  │ BT Listener  │    │
│  Joystick UI │                          │  │ → Command     │    │
│  Camera View │  ◄─── MJPEG Stream ───  │  │   Router      │    │
│  RSSI Meter  │                          │  └──────┬───────┘    │
└─────────────┘                           │         │            │
                                          │  ┌──────▼───────┐    │
                                          │  │ Phase-1       │    │
                                          │  │ Locomotion    │    │
                                          │  │ (Arduino)     │    │
                                          │  └──────────────┘    │
                                          └──────────────────────┘
```

---

## Bluetooth Protocol Design (Draft)

### Command Format (Phone → Jetson)
```json
{"cmd": "move", "dir": "fwd", "speed": 0.7}
{"cmd": "voice", "action": "stop"}
{"cmd": "mode", "value": "rc"}
{"cmd": "mode", "value": "follow"}
{"cmd": "ping"}
```

### Status Format (Jetson → Phone)
```json
{"type": "status", "mode": "follow", "target_locked": true, "battery": 78}
{"type": "ack", "cmd": "voice", "action": "stop", "ok": true}
{"type": "stream_url", "url": "http://192.168.x.x:8080/stream"}
```

---

## Dependencies on Previous Phases

| Dependency | From | Required For |
|-----------|------|-------------|
| Serial command protocol | Phase 1 | RC mode motor control |
| Ultrasonic obstacle avoidance | Phase 1 | Safe BT-guided navigation |
| YOLO detection pipeline | Phase 2 | Follow-me ↔ BT-nav handoff |
| Jetson camera access | Phase 2 | Livestream to phone |

---

## Folder Structure (Planned)

```
phase-3/
├── README.md                  # This file
├── android/                   # Android Studio project
│   ├── app/
│   │   ├── src/main/
│   │   │   ├── java/...       # Kotlin source
│   │   │   ├── res/           # Layouts, drawables
│   │   │   └── AndroidManifest.xml
│   │   └── build.gradle
│   └── build.gradle
├── jetson/                    # Jetson-side BT service
│   ├── bt_server.py           # Bluetooth SPP/BLE listener
│   ├── command_router.py      # Route BT commands to locomotion/camera
│   ├── camera_stream.py       # MJPEG or WebRTC server
│   └── config.yaml            # BT pairing, stream settings
└── docs/                      # Design docs, protocol specs
    ├── bt_protocol.md
    └── architecture.md
```

---

## TODO

- [ ] Decide: Bluetooth Classic (SPP) vs BLE vs hybrid
- [ ] Decide: camera streaming protocol (MJPEG vs WebRTC vs GStreamer)
- [ ] Decide: Android framework (Jetpack Compose vs Flutter vs React Native)
- [ ] Prototype BT pairing between phone and Jetson
- [ ] Implement basic command send/receive
- [ ] Build RC joystick UI
- [ ] Integrate camera livestream
- [ ] Implement RSSI-based navigation logic
- [ ] Add STT voice command pipeline
- [ ] End-to-end integration with Phase 1 + Phase 2
