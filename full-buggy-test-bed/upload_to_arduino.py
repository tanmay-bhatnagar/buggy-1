#!/usr/bin/env python3
"""
upload_to_arduino.py — Jetson-friendly Arduino uploader for UNO R4 WiFi.

What it does (TL;DR):
- Finds your Arduino board (stable /dev/serial/by-id/* preferred).
- Picks a sketch (newest .ino under ./arduino/ unless --sketch is provided).
- Compiles and uploads via arduino-cli with clear, copy-pasteable logs.
- Optional: opens a serial monitor after upload.

Why this exists:
- Avoid fragile, ever-changing terminal incantations.
- Make reassembly days painless: plug, run, done.

Hardware notes we'll mirror in the SoT doc:
- L293D shield + servo power domains: use separate motor power, tie grounds.
- Beware VIN jumper back-feed; confirm jumper position for your shield.
- Servos can share timer/PWM rails; prefer external 5–6V rail for servos.

Author: You (with a tiny robotic nudge)
"""

import argparse
import os
import sys
import subprocess
from pathlib import Path
from glob import glob
from typing import List, Optional, Tuple

# Defaults tuned for UNO R4 WiFi
DEFAULT_ARDUINO_DIR = Path("./arduino")
DEFAULT_FQBN = "arduino:renesas_uno:unor4wifi"
DEFAULT_BAUD = 115200
ARDUINO_CLI = "arduino-cli"

# -------- Utilities -------- #

def run_cmd(cmd: List[str], verbose: bool = True, dry_run: bool = False) -> Tuple[int, str, str]:
    """Run a shell command and return (returncode, stdout, stderr)."""
    if verbose or dry_run:
        print(f"\n$ {' '.join(cmd)}")
    if dry_run:
        return 0, "", ""
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.stdout:
        print(proc.stdout.strip())
    if proc.returncode != 0:
        # Keep stderr visible; add common helpful hints.
        if proc.stderr:
            print(proc.stderr.strip(), file=sys.stderr)
        # Permission hints for serial devices
        if "Permission denied" in (proc.stderr or "") or "cannot open" in (proc.stderr or ""):
            print(
                "\nHint: Serial permission issue detected.\n"
                "  Try:  sudo usermod -aG dialout $USER  # then log out/in or reboot\n",
                file=sys.stderr
            )
    return proc.returncode, proc.stdout, proc.stderr


def assert_arduino_cli_available() -> None:
    """Ensure arduino-cli is on PATH and callable."""
    try:
        rc, out, _ = run_cmd([ARDUINO_CLI, "version"], verbose=False)
        if rc != 0:
            raise RuntimeError("arduino-cli not callable.")
    except FileNotFoundError:
        raise RuntimeError(
            "arduino-cli not found on PATH.\n"
            "Install: curl -fsSL https://raw.githubusercontent.com/arduino/arduino-cli/master/install.sh | sh\n"
            "         sudo mv bin/arduino-cli /usr/local/bin/"
        )


def core_is_installed(fqbn: str, verbose: bool = False) -> bool:
    """Check that the core for the given FQBN family is installed."""
    family = fqbn.split(":")[0]  # 'arduino'
    rc, out, _ = run_cmd([ARDUINO_CLI, "core", "list"], verbose=verbose)
    return rc == 0 and "arduino:renesas_uno" in (out or "")


def find_candidate_ports() -> List[Path]:
    """Return candidate serial device paths, preferring /dev/serial/by-id/*."""
    by_id = sorted(map(Path, glob("/dev/serial/by-id/*")))
    # Prefer anything that mentions Arduino if available
    arduinoish = [p for p in by_id if any(s in p.name.lower() for s in ["arduino", "uno", "r4", "renesas"])]
    if arduinoish:
        return arduinoish
    if by_id:
        return by_id

    # Fallback to ttyACM*/ttyUSB* sorted by mtime (newest last)
    tty = [Path(p) for p in glob("/dev/ttyACM*")] + [Path(p) for p in glob("/dev/ttyUSB*")]
    tty = [p for p in tty if p.exists()]
    tty.sort(key=lambda p: p.stat().st_mtime)
    return tty


def pick_port(user_port: Optional[str]) -> Path:
    """Pick a serial port, verifying existence."""
    if user_port:
        p = Path(user_port)
        if not p.exists():
            raise FileNotFoundError(f"--port '{user_port}' does not exist.")
        return p

    ports = find_candidate_ports()
    if not ports:
        raise FileNotFoundError(
            "No serial devices found.\n"
            "Tips:\n"
            "  • Use a data-capable USB-C cable.\n"
            "  • Run: arduino-cli board list\n"
            "  • Or pass --port /dev/serial/by-id/… explicitly."
        )
    # Take the newest candidate
    return ports[-1]


def is_valid_sketch_dir(path: Path) -> bool:
    """An Arduino sketch dir is valid if it contains <dir>/<dir>.ino."""
    if not path.is_dir():
        return False
    ino = path / f"{path.name}.ino"
    return ino.exists()


def find_latest_sketch(arduino_root: Path) -> Path:
    """Find the most recently modified valid sketch under arduino_root."""
    if not arduino_root.exists():
        raise FileNotFoundError(f"Arduino root '{arduino_root}' not found.")
    candidates: List[Tuple[float, Path]] = []
    for ino_path in arduino_root.rglob("*.ino"):
        sketch_dir = ino_path.parent
        if is_valid_sketch_dir(sketch_dir):
            mtime = ino_path.stat().st_mtime
            candidates.append((mtime, sketch_dir))
        else:
            print(f"Warning: {ino_path} is not named {sketch_dir.name}.ino — skipping.", file=sys.stderr)
    if not candidates:
        raise FileNotFoundError(
            f"No valid sketches under '{arduino_root}'.\n"
            "Sketch layout must be: <SketchName>/<SketchName>.ino"
        )
    candidates.sort(key=lambda t: t[0])
    return candidates[-1][1]


def resolve_sketch_path(sketch_arg: Optional[str], arduino_root: Path) -> Path:
    """Resolve the sketch directory from --sketch (dir or .ino) or pick latest."""
    if sketch_arg:
        p = Path(sketch_arg).resolve()
        if p.is_file() and p.suffix.lower() == ".ino":
            p = p.parent
        if not is_valid_sketch_dir(p):
            raise ValueError(
                f"'{p}' is not a valid sketch directory.\n"
                f"Expected: {p.name}/{p.name}.ino"
            )
        return p
    return find_latest_sketch(arduino_root)


# -------- Actions -------- #

def compile_sketch(sketch_dir: Path, fqbn: str, verbose: bool, dry_run: bool) -> None:
    cmd = [ARDUINO_CLI, "compile", "--fqbn", fqbn, str(sketch_dir)]
    rc, _, _ = run_cmd(cmd, verbose=verbose, dry_run=dry_run)
    if rc != 0 and not dry_run:
        raise RuntimeError("Compilation failed.")


def upload_sketch(sketch_dir: Path, fqbn: str, port: Path, verbose: bool, dry_run: bool) -> None:
    cmd = [ARDUINO_CLI, "upload", "-p", str(port), "-b", fqbn, str(sketch_dir)]
    rc, _, _ = run_cmd(cmd, verbose=verbose, dry_run=dry_run)
    if rc != 0 and not dry_run:
        raise RuntimeError("Upload failed.")


def open_serial_monitor(port: Path, baud: int, verbose: bool, dry_run: bool) -> None:
    print(f"\nOpening serial monitor at {baud} baud. Press Ctrl+C to exit.")
    cmd = [ARDUINO_CLI, "monitor", "-p", str(port), "-c", f"baudrate={baud}"]
    try:
        run_cmd(cmd, verbose=verbose, dry_run=dry_run)
    except KeyboardInterrupt:
        print("\nSerial monitor closed.")


# -------- Main -------- #

def main():
    parser = argparse.ArgumentParser(
        description="Compile & upload Arduino sketches to UNO R4 WiFi from a Jetson. "
                    "Defaults to the newest sketch under ./arduino/."
    )
    parser.add_argument("--sketch", type=str, help="Path to sketch dir or .ino (must follow <name>/<name>.ino).")
    parser.add_argument("--port", type=str, help="Serial port (e.g., /dev/serial/by-id/usb-...).")
    parser.add_argument("--fqbn", type=str, default=DEFAULT_FQBN, help=f"Fully Qualified Board Name. Default: {DEFAULT_FQBN}")
    parser.add_argument("--baud", type=int, default=DEFAULT_BAUD, help=f"Baudrate for --monitor. Default: {DEFAULT_BAUD}")
    parser.add_argument("--monitor", action="store_true", help="Open serial monitor after upload.")
    parser.add_argument("--arduino-root", type=str, default=str(DEFAULT_ARDUINO_DIR),
                        help=f"Root folder for sketches. Default: {DEFAULT_ARDUINO_DIR}")
    parser.add_argument("--dry-run", action="store_true", help="Print commands without executing.")
    parser.add_argument("--verbose", action="store_true", help="More logging.")
    args = parser.parse_args()

    try:
        assert_arduino_cli_available()

        if not core_is_installed(args.fqbn, verbose=args.verbose):
            print(
                "\nThe UNO R4 core doesn't appear to be installed.\n"
                "Install it with:\n"
                "  arduino-cli core update-index && arduino-cli core install arduino:renesas_uno\n",
                file=sys.stderr
            )

        arduino_root = Path(args.arduino_root).resolve()
        sketch_dir = resolve_sketch_path(args.sketch, arduino_root)
        print(f"\nSketch: {sketch_dir} (expecting {sketch_dir.name}/{sketch_dir.name}.ino)")

        port = pick_port(args.port)
        print(f"Port:   {port}")

        fqbn = args.fqbn
        print(f"FQBN:   {fqbn}")

        compile_sketch(sketch_dir, fqbn, verbose=args.verbose, dry_run=args.dry_run)
        upload_sketch(sketch_dir, fqbn, port, verbose=args.verbose, dry_run=args.dry_run)

        if args.monitor:
            open_serial_monitor(port, args.baud, verbose=args.verbose, dry_run=args.dry_run)

        print("\n✅ Done.")

    except Exception as e:
        print(f"\n❌ {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()