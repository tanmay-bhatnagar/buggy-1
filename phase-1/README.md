# Phase 1 — Autonomous, Obstacle-Aware Locomotion

Phase 1 establishes the buggy's motion foundation: a Jetson Orin Nano makes high-level decisions and an Arduino UNO R4 WiFi executes motor, servo, and ultrasonic-sensor control over USB serial.

## Status

Completed as a physically iterated indoor prototype. The code includes autonomous obstacle response, telemetry, configuration profiles, and link-loss stopping. It should be treated as a prototype control stack, not a general navigation system.

## Architecture

```text
Jetson Python policy ── USB serial ──> Arduino firmware ──> HW-130/L293D shield ──> four DC motors
       ^                                      │
       └──────── ultrasonic / servo telemetry ┘
```

- **Jetson:** runs the policy, logging, configuration loading, and serial heartbeat.
- **Arduino:** runs non-blocking motion, servo, ultrasonic, serial protocol, status, and watchdog modules.
- **Safety:** if the Arduino stops receiving a heartbeat for the configured timeout (600 ms by default), it commands a motor stop.

## Hardware

| Component | Implementation |
| --- | --- |
| Compute | Jetson Orin Nano |
| Microcontroller | Arduino UNO R4 WiFi |
| Drive | Four DC motors through HW-130 / L293D + 74HC595 shield |
| Range sensing | HC-SR04 ultrasonic sensor on a pan servo |
| Serial defaults | `/dev/ttyACM0`, 115200 baud |

The motor supply must be correctly rated and separate from Jetson compute power; establish a shared ground and keep a physical power cut-off available.

## Code map

```text
arduino/BuggyPhase1/      Arduino sketch and modular firmware
jetson/app/               Control policy, sensing, serial link, watchdog, telemetry
jetson/config/            Default, home, and floor-surface profiles
jetson/scripts/           Launch and serial diagnostics
jetson/systemd/           Service template; paths require local edits before use
```

## Bring-up

1. Keep wheels off the ground for first tests.
2. Install the Arduino UNO R4 core and flash the firmware:

   ```bash
   arduino-cli core update-index
   arduino-cli core install arduino:renesas_uno
   python3 upload_to_arduino.py --sketch phase-1/arduino/BuggyPhase1 --port /dev/ttyACM0 --baud 115200
   ```

3. On the Jetson, install the small runtime dependency set:

   ```bash
   python3 -m venv .venv
   .venv/bin/pip install -r phase-1/jetson/requirements.txt
   ```

4. Check the serial link, then run a conservative profile:

   ```bash
   python3 phase-1/jetson/scripts/diagnose_serial.py
   bash phase-1/jetson/scripts/start.sh --profile carpet
   ```

Use `--profile tile`, `--profile carpet`, or `--profile outdoors`; custom YAML can be supplied with `--config`. Read the profile before running it on a real surface.

## Engineering constraints and limitations

- On this UNO R4 / shield combination, a Servo-versus-OE timer conflict means the motor-enable line is effectively binary. The code's speed/arc behavior is software pulsing rather than independent per-wheel PWM.
- The ultrasonic scan is a short, configuration-driven probe; it is not mapping, localization, or a guarantee of obstacle avoidance.
- Never install `jetson/systemd/buggy.service` unchanged: its working directory is a template and must be updated for the actual clone path and Python environment.

For the original detailed design and tuning notes, see [phase_1_readme.md](phase_1_readme.md). For recorded completion observations and hardware constraints, see [phase_1_completion_notes.md](phase_1_completion_notes.md).
