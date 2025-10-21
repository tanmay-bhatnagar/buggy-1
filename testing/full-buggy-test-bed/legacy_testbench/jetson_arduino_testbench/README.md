# Jetson <> Arduino Testbench Terminal

## Setup
1. Flash `buggy_testbench.ino` to your UNO R4 WiFi (board FQBN `arduino:renesas_uno:unor4wifi`).
2. On Jetson: `conda activate buggy`
3. Run: `./jetson/terminal.py /dev/ttyACM0`  (or omit the port to auto-detect)

## Commands
- `forward <secs> [speed]`
- `back <secs> [speed]`
- `left <secs> [speed]`
- `right <secs> [speed]`
- `spin_cw <secs> [speed]`
- `spin_ccw <secs> [speed]`
- `stop <secs>`
- `ultrasound on <secs> [spin on|off]`
- `abort`
- `help`, `exit`

While a command is active, the prompt is locked. Only `abort` is honored.

## Serial protocol (for reference)
Host -> Arduino:
- `MOVE <MODE> <SECS> [SPEED]`
- `ULTRASONIC ON <SECS> SPIN <ON|OFF>`
- `ABORT`

Arduino -> Host:
- `STATUS READY`
- `EVENT START ...`
- `DATA ULS <cm> <angle> <t_ms>`
- `EVENT COMPLETE ...`
- `EVENT ABORTED`
- `ERROR BUSY`

