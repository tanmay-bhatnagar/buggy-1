# Phase 3: Bluetooth Companion App (Android)

Bluetooth-connected Android app for remote control, camera streaming, and voice commands on the follow-me buggy — built in three sequential sub-phases.

---

## ⚠️ Current Status

| Sub-Phase | Focus | Status |
|-----------|-------|--------|
| **3A** | RC Locomotion Control (App → Buggy) | 🟢 DPad UI built, BT link pending |
| **3B** | Camera Streaming (Buggy → App) | ⏳ Pending |
| **3C** | Voice Commands (App → Buggy) | 🟢 STT UI built, SLM + BT pending |

---

## Overview

| Component | Details |
|-----------|---------|
| **Platform** | Android (Kotlin / Jetpack Compose) |
| **Connectivity** | Bluetooth Classic (SPP) |
| **Target Device** | Jetson Orin Nano (via External Dongle) |
| **Backdoor** | Arduino UNO R4 (ESP32-S3) as secondary gateway |
| **Camera Feed** | MJPEG Stream via Jetson (Phase 3B) |

---

## Sub-Phase 3A — RC Locomotion Control

> **Goal:** Drive the buggy from your phone like an RC car, with no autonomous logic involved.

This is the first thing to get working end-to-end. No camera, no voice — just reliable bidirectional control over Bluetooth.

### What's needed

- **App side**
  - D-Pad or virtual joystick UI (D-Pad already built)
  - Send directional commands over Bluetooth Classic (SPP)
  - Real-time connection status indicator
  - Speed control (e.g. slider or hold-to-accelerate)

- **Jetson side**
  - `bt_server.py`: Bluetooth SPP listener, accepts JSON commands
  - `command_router.py`: maps received commands to serial messages for the Arduino
  - Reuse existing Phase 1 serial protocol (`F`, `B`, `L`, `R`, `S`)

- **Protocol (Phone → Jetson)**
  ```json
  {"cmd": "move", "dir": "fwd", "speed": 0.7}
  {"cmd": "move", "dir": "left", "speed": 0.5}
  {"cmd": "move", "dir": "stop"}
  {"cmd": "ping"}
  ```

- **Protocol (Jetson → Phone)**
  ```json
  {"type": "ack", "cmd": "move", "ok": true}
  {"type": "status", "mode": "rc", "battery": 78}
  ```

### Milestone: 3A Complete
- [ ] Phone connects to Jetson over Bluetooth Classic (SPP)
- [ ] D-Pad commands drive the buggy in real-time
- [ ] Jetson echoes ack/status back to phone
- [ ] Stable at reasonable range (≥ 5m)

---

## Sub-Phase 3B — Camera Streaming

> **Goal:** See what the buggy sees, live on the phone. Toggle YOLO overlay on/off from the app.

Builds on 3A. The Bluetooth link is already up — this adds a parallel video stream.

### What's needed

- **App side**
  - Camera view panel in the RC screen (PiP or full-screen toggle)
  - "Model On / Off" toggle button — sends mode switch command to Jetson
  - Display MJPEG stream in `WebView` or custom `SurfaceView`

- **Jetson side**
  - `camera_stream.py`: MJPEG server (e.g. `cv2` + Flask or `mjpg-streamer`)
  - **Mode: raw** — pipe raw camera frames to stream
  - **Mode: YOLO** — run inference, draw bounding boxes, pipe annotated frames
  - Accept toggle command from BT channel: `{"cmd": "stream_mode", "value": "raw"}` / `"yolo"`
  - Send stream URL to phone on connect: `{"type": "stream_url", "url": "http://192.168.x.x:8080/stream"}`

- **Protocol additions**
  ```json
  {"cmd": "stream_mode", "value": "raw"}
  {"cmd": "stream_mode", "value": "yolo"}
  ```

### Streaming options (pick one)
| Option | Latency | Complexity | Notes |
|--------|---------|------------|-------|
| MJPEG via Flask | Medium | Low | Easiest to start |
| `mjpg-streamer` | Low | Low | Dedicated tool, very stable |
| GStreamer | Very Low | High | Best perf, harder setup |
| WebRTC | Very Low | Very High | Overkill for now |

**Recommendation:** Start with MJPEG via Flask, upgrade to `mjpg-streamer` if latency is unacceptable.

### Milestone: 3B Complete
- [ ] Live camera feed visible on phone while driving
- [ ] "Model On" shows YOLO bounding boxes on stream
- [ ] "Model Off" shows clean raw feed
- [ ] Toggle is near-instant (< 1s switch time)

---

## Sub-Phase 3C — Voice Commands

> **Goal:** Issue natural voice commands to the buggy hands-free.

Builds on 3A (BT link) and optionally 3B (can display feedback on stream).

### What's needed

- **App side**
  - Push-to-talk or always-on mic button
  - STT via Android native `SpeechRecognizer` (already built)
  - Intent parsing: keyword match on phone before sending
  - Optional: On-device SLM for fuzzy intent matching
  - Visual feedback: recognized text + command dispatched

- **Jetson side**
  - Handle `voice` command type in `command_router.py`
  - Map intent → motor/system action

- **Command vocabulary**
  | Phrase | Intent | Action |
  |--------|--------|--------|
  | "stop" / "halt" | STOP | Send stop to Arduino |
  | "come here" / "follow me" | FOLLOW | Switch to Phase 2 YOLO follow mode |
  | "go home" | HOME | Navigate back to start (future) |
  | "faster" / "speed up" | SPEED_UP | Increment speed |
  | "slower" / "slow down" | SPEED_DOWN | Decrement speed |
  | "RC mode" | RC | Switch to manual RC mode |

- **Protocol**
  ```json
  {"cmd": "voice", "action": "stop"}
  {"cmd": "voice", "action": "follow"}
  {"cmd": "voice", "action": "speed_up"}
  {"cmd": "mode", "value": "rc"}
  {"cmd": "mode", "value": "follow"}
  ```

### Milestone: 3C Complete
- [ ] Voice command recognized correctly on phone
- [ ] Intent sent over BT, buggy responds
- [ ] "Follow me" switches buggy to Phase 2 YOLO mode
- [ ] "Stop" reliably halts the buggy

---

## Architecture (High-Level)

```
┌──────────────────────┐        Bluetooth Classic (SPP)       ┌──────────────────────┐
│   Android App         │  ◄──────────────────────────────►   │   Jetson Orin Nano   │
│                       │                                      │                      │
│  [3A] D-Pad / Joystick│  ── {"cmd": "move", ...} ────────►  │  bt_server.py        │
│  [3B] Camera View     │  ◄── MJPEG stream (HTTP) ─────────  │  camera_stream.py    │
│       Model Toggle    │  ── {"cmd": "stream_mode"} ───────►  │                      │
│  [3C] STT / Voice     │  ── {"cmd": "voice", ...} ────────►  │  command_router.py   │
│                       │  ◄── {"type": "ack/status"} ───────  │       │              │
└──────────────────────┘                                      │       ▼              │
                                                              │  Phase 1 Arduino     │
                                                              │  (Serial: F/B/L/R/S) │
                                                              └──────────────────────┘
```

---

## Dependencies on Previous Phases

| Dependency | From | Required For |
|-----------|------|-------------|
| Serial command protocol (F/B/L/R/S) | Phase 1 | 3A RC motor control |
| Ultrasonic obstacle avoidance | Phase 1 | Safe operation in all modes |
| YOLO detection pipeline | Phase 2 | 3B model overlay, 3C follow-me voice cmd |
| Jetson camera access | Phase 2 | 3B livestream |

---

## Folder Structure (Planned)

```
phase-3/
├── README.md                    # This file
├── android/                     # Android Studio project
│   ├── app/
│   │   ├── src/main/
│   │   │   ├── java/...         # Kotlin source
│   │   │   ├── res/             # Layouts, drawables
│   │   │   └── AndroidManifest.xml
│   │   └── build.gradle
│   └── build.gradle
├── jetson/
│   ├── bt_server.py             # [3A] Bluetooth SPP listener
│   ├── command_router.py        # [3A/3C] Route commands → Arduino / modes
│   ├── camera_stream.py         # [3B] MJPEG stream server
│   └── config.yaml              # BT pairing, stream settings, ports
└── docs/
    ├── bt_protocol.md           # Full protocol spec
    └── architecture.md
```

---

## TODO

### 3A — RC Control
- [x] Build D-Pad UI in app
- [ ] Implement Bluetooth Classic (SPP) pairing and connection
- [ ] Send movement commands from app to Jetson
- [ ] Write `bt_server.py` on Jetson
- [ ] Write `command_router.py` — translate BT cmds to serial
- [ ] End-to-end test: D-Pad drives the buggy

### 3B — Camera Streaming
- [ ] Decide streaming protocol (MJPEG/Flask recommended first)
- [ ] Write `camera_stream.py` on Jetson (raw mode)
- [ ] Add YOLO inference mode to stream
- [ ] Add model toggle command handling (`stream_mode`)
- [ ] Display stream in app (WebView or SurfaceView)
- [ ] Add toggle button in app UI

### 3C — Voice Commands
- [x] Build STT UI in app (Android Native SpeechRecognizer)
- [ ] Implement keyword/intent matching on phone
- [ ] Send voice command over BT channel
- [ ] Handle `voice` commands in `command_router.py`
- [ ] End-to-end test: voice → BT → buggy responds
- [ ] (Optional) Add on-device SLM for fuzzy intent parsing
