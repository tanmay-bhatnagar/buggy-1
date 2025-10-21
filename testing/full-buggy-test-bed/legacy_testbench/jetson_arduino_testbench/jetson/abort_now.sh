#!/usr/bin/env bash
set -euo pipefail
PORT="${1:-/dev/ttyACM0}"
python3 - <<PY
import serial, sys
ser = serial.Serial("$PORT", 115200, timeout=0.2)
ser.write(b"ABORT\\n")
ser.flush()
ser.close()
print("ABORT sent on", "$PORT")
PY
