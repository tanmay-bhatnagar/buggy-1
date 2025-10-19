#!/usr/bin/env python3
"""
upload_to_arduino.py — Jetson-friendly Arduino uploader for UNO R4 WiFi

This script DOES NOT touch or modify your .ino files. It only:
  • Finds your board port (prefers /dev/serial/by-id/*)
  • Picks a sketch (default = newest valid ./arduino/<Name>/<Name>.ino)
  • Compiles & uploads using arduino-cli
  • (Optional) Opens a serial monitor at the chosen baud

Usage examples (from repo root):
  python3 upload_to_arduino.py
  python3 upload_to_arduino.py --sketch ./arduino/MovementTest --monitor
  python3 upload_to_arduino.py --sketch ./arduino/MovementTest --port /dev/serial/by-id/usb-Arduino_UNO_WiFi_R4_... --verbose
  python3 upload_to_arduino.py --dry-run

Flags:
  --sketch <path>       Sketch dir or .ino (must be Name/Name.ino)
  --port <device>       Serial device (auto-detects if omitted)
  --fqbn <fqbn>         Board (default: arduino:renesas_uno:unor4wifi)
  --baud <int>          Serial monitor baud (default: 115200)
  --monitor             Open arduino-cli monitor after upload
  --arduino-root <dir>  Root to search for sketches (default: ./arduino)
  --dry-run             Print commands but don’t execute
  --verbose             More logging
"""
from __future__ import annotations
import argparse
import os
import sys
import subprocess
from pathlib import Path
from glob import glob
from typing import List, Optional, Tuple

# Defaults
DEFAULT_ARDUINO_DIR = Path("./arduino")
DEFAULT_FQBN = "arduino:renesas_uno:unor4wifi"
DEFAULT_BAUD = 115200
DEFAULT_PORT = "/dev/ttyACM0"  # Your known-good default
ARDUINO_CLI = "arduino-cli"

# ---------------- Utilities ---------------- #

def run_cmd(cmd: List[str], verbose: bool = True, dry_run: bool = False) -> Tuple[int, str, str]:
    """Run a command and return (rc, stdout, stderr)."""
    if verbose or dry_run:
        print("$ " + " ".join(cmd))
    if dry_run:
        return 0, "", ""
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.stdout:
        print(proc.stdout.rstrip())
    if proc.returncode != 0 and proc.stderr:
        print(proc.stderr.rstrip(), file=sys.stderr)
        if ("Permission denied" in proc.stderr) or ("cannot open" in proc.stderr):
            print("Hint: Serial permission issue. Try: sudo usermod -aG dialout $USER  # then log out/in or reboot", file=sys.stderr)
    return proc.returncode, proc.stdout, proc.stderr


def assert_arduino_cli_available() -> None:
    try:
        rc, _, _ = run_cmd([ARDUINO_CLI, "version"], verbose=False)
        if rc != 0:
            raise RuntimeError("arduino-cli not callable")
    except FileNotFoundError:
        raise RuntimeError(
            "arduino-cli not found on PATH. Install: curl -fsSL https://raw.githubusercontent.com/arduino/arduino-cli/master/install.sh | sh && sudo mv bin/arduino-cli /usr/local/bin/"
        )


def core_is_installed(fqbn: str, verbose: bool = False) -> bool:
    rc, out, _ = run_cmd([ARDUINO_CLI, "core", "list"], verbose=verbose)
    return rc == 0 and "arduino:renesas_uno" in (out or "")


def find_candidate_ports() -> List[Path]:
    by_id = sorted(map(Path, glob("/dev/serial/by-id/*")))
    arduinoish = [p for p in by_id if any(s in p.name.lower() for s in ("arduino", "uno", "r4", "renesas"))]
    if arduinoish:
        return arduinoish
    if by_id:
        return by_id
    tty = [Path(p) for p in glob("/dev/ttyACM*")] + [Path(p) for p in glob("/dev/ttyUSB*")]
    tty = [p for p in tty if p.exists()]
    tty.sort(key=lambda p: p.stat().st_mtime)
    return tty


def pick_port(user_port: Optional[str]) -> Path:
    # Priority: explicit flag > env var > DEFAULT_PORT (ttyACM0) > by-id/ACM scan
    env_port = os.environ.get("BUGGY_ARDUINO_PORT")
    if user_port:
        p = Path(user_port)
        if not p.exists():
            raise FileNotFoundError(f"--port '{user_port}' does not exist")
        return p
    if env_port:
        p = Path(env_port)
        if p.exists():
            return p
    dp = Path(DEFAULT_PORT)
    if dp.exists():
        return dp
    ports = find_candidate_ports()
    if not ports:
        raise FileNotFoundError(
            "No serial devices found. Tips: Use a data-capable USB-C cable; run 'arduino-cli board list'; or set BUGGY_ARDUINO_PORT=/dev/ttyACM0."
        )
    return ports[-1]


def is_valid_sketch_dir(path: Path) -> bool:
    return path.is_dir() and (path / f"{path.name}.ino").exists()


def find_latest_sketch(arduino_root: Path) -> Path:
    if not arduino_root.exists():
        raise FileNotFoundError(f"Arduino root '{arduino_root}' not found")
    candidates: List[Tuple[float, Path]] = []
    for ino_path in arduino_root.rglob("*.ino"):
        sketch_dir = ino_path.parent
        if is_valid_sketch_dir(sketch_dir):
            candidates.append((ino_path.stat().st_mtime, sketch_dir))
        else:
            print(f"Warning: {ino_path} is not {sketch_dir.name}.ino — skipping", file=sys.stderr)
    if not candidates:
        raise FileNotFoundError(
            f"No valid sketches under '{arduino_root}'. Layout must be <Name>/<Name>.ino"
        )
    candidates.sort(key=lambda t: t[0])
    return candidates[-1][1]


def resolve_sketch_path(sketch_arg: Optional[str], arduino_root: Path) -> Path:
    if sketch_arg:
        p = Path(sketch_arg).resolve()
        if p.is_file() and p.suffix.lower() == ".ino":
            p = p.parent
        if not is_valid_sketch_dir(p):
            raise ValueError(f"'{p}' is not a valid sketch folder (expected {p.name}/{p.name}.ino)")
        return p
    return find_latest_sketch(arduino_root)

# ---------------- Actions ---------------- #

def compile_sketch(sketch_dir: Path, fqbn: str, verbose: bool, dry_run: bool) -> None:
    cmd = [ARDUINO_CLI, "compile", "--fqbn", fqbn, str(sketch_dir)]
    rc, _, _ = run_cmd(cmd, verbose=verbose, dry_run=dry_run)
    if rc != 0 and not dry_run:
        raise RuntimeError("Compilation failed")


def upload_sketch(sketch_dir: Path, fqbn: str, port: Path, verbose: bool, dry_run: bool) -> None:
    cmd = [ARDUINO_CLI, "upload", "-p", str(port), "-b", fqbn, str(sketch_dir)]
    rc, _, _ = run_cmd(cmd, verbose=verbose, dry_run=dry_run)
    if rc != 0 and not dry_run:
        raise RuntimeError("Upload failed")


def open_serial_monitor(port: Path, baud: int, verbose: bool, dry_run: bool) -> None:
    print(f"Opening serial monitor at {baud} baud. Ctrl+C to exit.")
    cmd = [ARDUINO_CLI, "monitor", "-p", str(port), "-c", f"baudrate={baud}"]
    try:
        run_cmd(cmd, verbose=verbose, dry_run=dry_run)
    except KeyboardInterrupt:
        print("Serial monitor closed.")

def upload_sketch_with_retry(sketch_dir: Path, fqbn: str, port: Path, verbose: bool, dry_run: bool) -> Path:
    """Upload to the given port; on failure, retry common alternates and return the working port."""
    # 1st try: requested/selected port
    cmd = [ARDUINO_CLI, "upload", "-p", str(port), "-b", fqbn, str(sketch_dir)]
    rc, _, _ = run_cmd(cmd, verbose=verbose, dry_run=dry_run)
    if rc == 0 or dry_run:
        return port
    # Build alternates list
    alternates: List[Path] = []
    ps = str(port)
    if "/dev/serial/by-id/" in ps and "-if01" in ps:
        alternates.append(Path(ps.replace("-if01", "-if00")))
    alternates.extend(Path(p) for p in glob("/dev/ttyACM*"))
    for alt in alternates:
        if not alt.exists() or alt == port:
            continue
        if verbose:
            print(f"Retrying upload on {alt}...")
        cmd = [ARDUINO_CLI, "upload", "-p", str(alt), "-b", fqbn, str(sketch_dir)]
        rc2, _, _ = run_cmd(cmd, verbose=verbose, dry_run=dry_run)
        if rc2 == 0:
            return alt
    raise RuntimeError("Upload failed on all candidate ports")

# ---------------- Main ---------------- #

def main():
    parser = argparse.ArgumentParser(
        description=(
            "Compile & upload Arduino sketches to UNO R4 WiFi from a Jetson. Defaults to the newest sketch under ./arduino/."
        )
    )
    parser.add_argument("--sketch", type=str, help="Path to sketch dir or .ino (must follow <name>/<name>.ino)")
    parser.add_argument("--port", type=str, help="Serial port (e.g., /dev/serial/by-id/usb-...)")
    parser.add_argument("--fqbn", type=str, default=DEFAULT_FQBN, help=f"FQBN (default {DEFAULT_FQBN})")
    parser.add_argument("--baud", type=int, default=DEFAULT_BAUD, help=f"Baud for --monitor (default {DEFAULT_BAUD})")
    parser.add_argument("--monitor", action="store_true", help="Open serial monitor after upload")
    parser.add_argument("--arduino-root", type=str, default=str(DEFAULT_ARDUINO_DIR), help=f"Root for sketches (default {DEFAULT_ARDUINO_DIR})")
    parser.add_argument("--dry-run", action="store_true", help="Print commands without executing")
    parser.add_argument("--verbose", action="store_true", help="More logging")
    args = parser.parse_args()

    try:
        assert_arduino_cli_available()
        if not core_is_installed(args.fqbn, verbose=args.verbose):
            print("UNO R4 core not found. Install with: arduino-cli core update-index && arduino-cli core install arduino:renesas_uno", file=sys.stderr)
        arduino_root = Path(args.arduino_root).resolve()
        sketch_dir = resolve_sketch_path(args.sketch, arduino_root)
        print(f"Sketch: {sketch_dir} (expecting {sketch_dir.name}/{sketch_dir.name}.ino)")
        port = pick_port(args.port)
        print(f"Port: {port}")
        fqbn = args.fqbn
        print(f"FQBN: {fqbn}")

        compile_sketch(sketch_dir, fqbn, verbose=args.verbose, dry_run=args.dry_run)
        port = upload_sketch_with_retry(sketch_dir, fqbn, port, verbose=args.verbose, dry_run=args.dry_run)

        if args.monitor:
            open_serial_monitor(port, args.baud, verbose=args.verbose, dry_run=args.dry_run)

        print("Done.")

    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()

