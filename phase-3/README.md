# Phase 3 — Mobile Remote Control, Telemetry, and Video

Phase 3 adds a mobile companion to the buggy: an Android app sends manual movement commands to the Jetson over Bluetooth Classic, while the Jetson can publish a raw MJPEG camera stream over the local network.

## Status

| Capability | Status |
| --- | --- |
| Android Kotlin / Jetpack Compose app | Implemented. |
| Bluetooth Classic SPP client and Jetson server | Implemented, including reconnect and explicit D-pad stop handling. |
| D-pad → Jetson → Arduino movement path | Implemented in code; validate on the target hardware before operation. |
| Raw MJPEG server and camera snapshots | Implemented. |
| Android native speech-recognition UI | Implemented as UI; voice-to-command routing is not integrated. |
| YOLO camera overlay / stream-mode switching | Not implemented. |
| Autonomous follow-mode switching | Not implemented. |

## Architecture

```text
Android app ── Bluetooth Classic SPP / newline-delimited JSON ──> Jetson bt_server.py ── USB serial ──> Arduino
    │                                                                  │
    └────────── HTTP snapshot / raw MJPEG on trusted LAN ──────────────┴──── camera_stream.py
```

The Bluetooth control path maps `fwd`, `back`, `left`, `right`, and `stop` messages to the existing Arduino serial commands. Camera traffic is HTTP, not Bluetooth.

## Prerequisites

- A physical Android device (the project declares Bluetooth, microphone, and local-network permissions).
- Android Studio with an SDK compatible with `compileSdk 36`; the project uses Java 11 compatibility, `minSdk 24`, and `targetSdk 36`.
- Jetson Linux Bluetooth / BlueZ, Python, `pyserial`, a serial-connected Arduino, and OpenCV for camera streaming.
- A trusted local network for the camera stream. The server listens without authentication; never expose it publicly.

The Android source currently needs a target Jetson Bluetooth address and local camera URL appropriate to the deployment. Inspect and set those values for your own hardware before building; device discovery is not a completed app feature.

## Android build

```bash
cd android
./gradlew assembleDebug
```

The debug APK is written to `android/app/build/outputs/apk/debug/app-debug.apk`. Test Bluetooth and microphone permissions on a physical device.

## Jetson Bluetooth server

First verify wiring and serial control with the wheels elevated. A safe dry run does not open a real serial control path:

```bash
python3 jetson/bt_server.py --dry-run
```

For a real SPP session, configure the Jetson Bluetooth adapter, then start the server:

```bash
sudo sdptool add SP
sudo hciconfig hci0 piscan
python3 jetson/bt_server.py --port /dev/ttyACM0
```

Keep a physical power cut-off available. Do not rely solely on Bluetooth reconnect behavior, the serial heartbeat, or the ultrasonic sensor to make a test safe.

## Camera server

With a USB camera connected to the Jetson:

```bash
python3 jetson/camera_stream.py --source 0 --width 640 --height 480 --fps 20
```

The service defaults to port 8080 and exposes `/`, `/stream`, `/snapshot.jpg`, and `/health`. It serves a raw feed only; it does not run YOLO or provide an overlay toggle.

## Current limitations

- Voice recognition is an Android UI capability only; no intent parser or Bluetooth voice-command dispatch is wired into the Jetson control server.
- `mode` acknowledgements do not switch the buggy into autonomous-follow behavior.
- End-to-end remote-control behavior is hardware-dependent and must be revalidated after changes to the Arduino protocol, Jetson image, Android target address, or network.
- The camera stream is unauthenticated local HTTP. Restrict it to a trusted LAN.

For the original product exploration and future voice ideas, see [Voice Commands Plan.md](Voice%20Commands%20Plan.md). It is a planning document, not an implementation-status source.
