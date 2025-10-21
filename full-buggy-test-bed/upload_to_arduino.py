#!/usr/bin/env python3
"""
upload_to_arduino.py — compile, upload, and open a *bidirectional* serial monitor
Tested on Arduino UNO R4 WiFi (board fqbn: arduino:renesas_uno:unor4wifi).

Key extras vs many one-way monitors:
- stdin -> serial (sends what you type) with selectable line endings (--eol LF/CRLF/CR)
- serial -> stdout reader thread
- optional auto-detect of /dev/ttyACM* when --port not provided
- optional compile & upload using arduino-cli when --sketch is provided

Usage examples:
  python3 upload_to_arduino.py --sketch ./arduino/Servo_Movement/ --eol CRLF
  python3 upload_to_arduino.py --port /dev/ttyACM0 --baud 115200 --eol LF

Ctrl+C exits the monitor cleanly.
"""

import argparse
import os
import sys
import time
import glob
import subprocess
from shutil import which


def run(cmd, check=True, capture=False, cwd=None):
    print(f"[step] {' '.join(cmd)}")
    if capture:
        res = subprocess.run(cmd, cwd=cwd, check=check, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        print(res.stdout, end="")
        return res
    else:
        return subprocess.run(cmd, cwd=cwd, check=check)


def autodetect_port():
    # Prefer the most recently created /dev/ttyACM*
    candidates = sorted(glob.glob("/dev/ttyACM*"))
    if candidates:
        return candidates[-1]
    # Fallback to ttyUSB*
    candidates = sorted(glob.glob("/dev/ttyUSB*"))
    if candidates:
        return candidates[-1]
    return None


def ensure_pyserial():
    try:
        import serial  # noqa: F401
    except Exception:
        print("[info] installing pyserial…")
        run([sys.executable, "-m", "pip", "install", "--user", "pyserial"], check=True)


def reset_via_dtr(port, baud):
    ensure_pyserial()
    import serial
    try:
        s = serial.Serial(port, baudrate=baud, timeout=0.1)
        s.dtr = False
        time.sleep(0.05)
        s.dtr = True
        time.sleep(0.05)
        s.dtr = False
        s.close()
        print(f"[step] reset via DTR on {port}")
    except Exception as e:
        print(f"[warn] DTR reset failed: {e}")


def monitor_serial(port, baud, eol):
    ensure_pyserial()
    import serial
    import threading

    eol_map = {"LF": "\n", "CRLF": "\r\n", "CR": "\r"}
    tx_eol = eol_map.get(eol, "\n")

    print(f"[monitor] {port} @ {baud}  (Ctrl+C to exit; sending {eol})")
    s = serial.Serial(port, baudrate=baud, timeout=0.05)

    # UNO R4 may reset on port open; give it a moment
    time.sleep(0.3)

    stop = False

    def reader():
        nonlocal stop
        try:
            while not stop:
                try:
                    line = s.readline()
                    if line:
                        try:
                            sys.stdout.write(line.decode("utf-8", "ignore"))
                            sys.stdout.flush()
                        except Exception:
                            sys.stdout.write(repr(line) + "\n")
                            sys.stdout.flush()
                except Exception:
                    # brief backoff on read errors
                    time.sleep(0.02)
        finally:
            pass

    t = threading.Thread(target=reader, daemon=True)
    t.start()

    try:
        for line in sys.stdin:
            msg = line.rstrip("\r\n") + tx_eol
            s.write(msg.encode("utf-8", "ignore"))
    except KeyboardInterrupt:
        pass
    finally:
        stop = True
        try:
            s.close()
        except Exception:
            pass


def require_arduino_cli():
    if which("arduino-cli"):
        return
    print("[info] arduino-cli not found. Installing is recommended: https://arduino.github.io/arduino-cli/latest/installation/")
    raise SystemExit(2)


def compile_and_upload(sketch, fqbn, port, baud):
    require_arduino_cli()
    # Compile
    run(["arduino-cli", "compile", "--fqbn", fqbn, sketch], check=True)
    # Upload
    run(["arduino-cli", "upload", "-p", port, "--fqbn", fqbn, sketch], check=True)
    # Print hint
    print(f"[step] new upload port: {port} (serial)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sketch", help="Path to sketch folder to compile & upload (optional)")
    ap.add_argument("--port", help="Serial port (auto-detected if omitted)")
    ap.add_argument("--baud", type=int, default=115200, help="Monitor baud rate (default: 115200)")
    ap.add_argument("--fqbn", default="arduino:renesas_uno:unor4wifi", help="Fully qualified board name for arduino-cli")
    ap.add_argument("--no-upload", action="store_true", help="Skip compile/upload and only open monitor")
    ap.add_argument("--eol", choices=["LF", "CRLF", "CR"], default="LF", help="Line ending appended to each command")
    ap.add_argument("--dtr-reset", action="store_true", help="Toggle DTR to reset just before monitoring")
    args = ap.parse_args()

    port = args.port or autodetect_port()
    if not port:
        print("[error] could not detect a serial port; use --port /dev/ttyACM0")
        sys.exit(1)
    print(f"[info] using port: {port}")

    if args.sketch and not args.no_upload:
        if not os.path.isdir(args.sketch):
            print(f"[error] sketch folder not found: {args.sketch}")
            sys.exit(1)
        compile_and_upload(args.sketch, args.fqbn, port, args.baud)
        # Give the board time to reboot after upload
        time.sleep(0.5)

    if args.dtr_reset:
        reset_via_dtr(port, args.baud)
        time.sleep(0.2)

    print(f"[monitor] open {port} at {args.baud} (Ctrl+C to exit)")
    monitor_serial(port, args.baud, args.eol)


if __name__ == "__main__":
    main()

