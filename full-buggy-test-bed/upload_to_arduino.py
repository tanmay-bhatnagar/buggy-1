#!/usr/bin/env python3
# =============================================================================
# upload_to_arduino.py
#
# Purpose:
#   Compile an Arduino sketch, upload it to a connected board, force a clean
#   reset via DTR (so setup() banners print reliably), and open a live serial
#   monitor — all from the Jetson terminal.
#
# Prerequisites:
#   - arduino-cli is installed and in PATH
#   - Board core already installed (e.g., UNO R4 WiFi: arduino:renesas_uno)
#   - Sketch exists as a folder or .ino path
#
# Usage:
#   python3 upload_to_arduino.py --sketch <path> [--fqbn <FQBN>] [--port <PORT>]
#                                [--baud <115200>] [--no-monitor]
#
# Arguments:
#   --sketch       Path to the sketch folder (preferred) or .ino file.
#                  Example: --sketch ~/arduino/ServoTest
#   --fqbn         Fully Qualified Board Name (default: arduino:renesas_uno:unor4wifi).
#                  Example: --fqbn arduino:avr:uno
#   --port         Serial device path override. If not set, auto-detects from
#                  `arduino-cli board list` or falls back to /dev/ttyACM*/USB*.
#                  Example: --port /dev/ttyACM0
#   --baud         Monitor baud rate (default: 115200).
#   --no-monitor   Skip opening the serial monitor after upload (just program it).
#
# Typical examples:
#   # UNO R4 WiFi, auto-detect port, monitor at 115200:
#   python3 upload_to_arduino.py --sketch ~/arduino/ServoTest
#
#   # Specify FQBN and port explicitly:
#   python3 upload_to_arduino.py --sketch ~/arduino/ServoTest \
#       --fqbn arduino:renesas_uno:unor4wifi --port /dev/ttyACM0
#
# Notes:
#   - The script ensures read/write permissions on the serial device (chmod a+rw)
#     for the current session. For a permanent fix, add a udev rule separately.
#   - After upload, Linux may recreate the tty node; we re-detect and re-apply perms.
#   - We pulse DTR before monitoring so the board re-enumerates setup() and prints
#     your startup lines every run (no “silent first line” problem).
# =============================================================================

import argparse, subprocess, sys, time, os, glob, shutil

# -------- small helpers --------
def run(cmd, check=True, capture=False, text=True):
    return subprocess.run(cmd, check=check, capture_output=capture, text=text)

def which_or_die(binname):
    if shutil.which(binname) is None:
        sys.exit(f"[error] '{binname}' not found in PATH")

def detect_port(prefer=None):
    if prefer and os.path.exists(prefer):
        return prefer
    try:
        out = run(["arduino-cli", "board", "list"], capture=True).stdout.splitlines()
        for line in out:
            if "/dev/tty" in line and ("ACM" in line or "USB" in line):
                return line.split()[0]
    except Exception:
        pass
    for pat in ("/dev/ttyACM*", "/dev/ttyUSB*"):
        matches = sorted(glob.glob(pat))
        if matches:
            return matches[0]
    return None

def ensure_perms(port):
    try:
        with open(port, "rb"):
            return
    except PermissionError:
        print(f"[info] fixing permissions on {port} (sudo may prompt)…")
        run(["sudo", "chmod", "a+rw", port], check=False)

def compile_sketch(sketch, fqbn):
    print(f"[step] compile: {sketch} [{fqbn}]")
    run(["arduino-cli", "compile", "--fqbn", fqbn, sketch])

def upload_sketch(sketch, fqbn, port):
    print(f"[step] upload → {port}")
    run(["arduino-cli", "upload", "-p", port, "--fqbn", fqbn, sketch])

def pulse_dtr(port, baud):
    try:
        import serial
    except ImportError:
        print("[info] installing pyserial for monitor…")
        run([sys.executable, "-m", "pip", "install", "--user", "pyserial"])
        import serial
    print(f"[step] reset via DTR on {port}")
    s = serial.Serial(port, baud, timeout=1)
    s.dtr = False; time.sleep(0.2); s.dtr = True; time.sleep(0.4)
    s.close()

def monitor_serial(port, baud):
    try:
        import serial
    except ImportError:
        print("[info] installing pyserial for monitor…")
        run([sys.executable, "-m", "pip", "install", "--user", "pyserial"])
        import serial
    print(f"[monitor] {port} @ {baud}  (Ctrl+C to exit)")
    s = serial.Serial(port, baud, timeout=1)
    try:
        while True:
            line = s.readline()
            if line:
                try:
                    print(line.decode("utf-8", "ignore").rstrip())
                except:
                    print(repr(line))
    except KeyboardInterrupt:
        pass
    finally:
        s.close()

# -------- main --------
def main():
    which_or_die("arduino-cli")

    ap = argparse.ArgumentParser(description="Compile → Upload → Reset (DTR) → Monitor")
    ap.add_argument("--sketch", required=True, help="Path to sketch folder or .ino")
    ap.add_argument("--fqbn", default="arduino:renesas_uno:unor4wifi",
                    help="Fully Qualified Board Name (default: UNO R4 WiFi)")
    ap.add_argument("--port", default=None, help="Serial port (override autodetect)")
    ap.add_argument("--baud", type=int, default=115200, help="Monitor baud (default 115200)")
    ap.add_argument("--no-monitor", action="store_true", help="Skip live monitor after upload")
    args = ap.parse_args()

    port = detect_port(args.port)
    if not port:
        sys.exit("[error] No serial port found. Plug the board and try again.")

    print(f"[info] using port: {port}")
    ensure_perms(port)

    compile_sketch(args.sketch, args.fqbn)
    upload_sketch(args.sketch, args.fqbn, port)

    # tty node can bounce after upload → re-detect and re-apply perms
    time.sleep(0.5)
    new_port = detect_port(args.port) or port
    if new_port != port:
        print(f"[info] port changed: {port} → {new_port}")
    port = new_port
    ensure_perms(port)

    pulse_dtr(port, args.baud)

    if args.no_monitor:
        print("[done] upload complete (monitor disabled)")
    else:
        monitor_serial(port, args.baud)

if __name__ == "__main__":
    main()

