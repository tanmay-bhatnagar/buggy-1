#!/usr/bin/env python3
"""
bt_server.py — Bluetooth SPP listener for the buggy.

Uses native Python AF_BLUETOOTH sockets (no pybluez dependency).
Accepts one Android client at a time over RFCOMM (Serial Port Profile).
Receives JSON commands and routes them to the Arduino via serial.

Setup (run once on Jetson):
    sudo sdptool add SP                    # register SPP service in SDP
    sudo hciconfig hci0 piscan             # make discoverable + connectable

Usage:
    python3 bt_server.py                   # normal mode
    python3 bt_server.py --dry-run         # log only, no serial
    python3 bt_server.py --port /dev/ttyACM1  # custom serial port

Protocol (Phone → Jetson):
    {"cmd": "move", "dir": "fwd", "speed": 0.7}
    {"cmd": "move", "dir": "stop"}
    {"cmd": "ping"}
    {"type": "remote", "direction": "forward"}   (DPad format)

Protocol (Jetson → Phone):
    {"type": "ack", "cmd": "move", "ok": true}
    {"type": "status", "mode": "rc", "battery": -1}
"""

import argparse
import json
import signal
import socket
import sys
import time

try:
    import serial
except ImportError:
    serial = None
    print("⚠️  pyserial not installed — forcing dry-run mode")

# ── Config ──────────────────────────────────────────────────────────────────

RFCOMM_CHANNEL = 1          # RFCOMM channel (1 is standard for SPP)
DEFAULT_SERIAL_PORT = "/dev/ttyACM0"
BAUD_RATE = 9600

# Direction → Arduino serial character (Phase 1 protocol)
DIR_MAP = {
    "fwd":     "F",
    "forward": "F",
    "rev":     "B",
    "reverse": "B",
    "back":    "B",
    "left":    "L",
    "right":   "R",
    "stop":    "S",
}

# ── Globals ─────────────────────────────────────────────────────────────────

running = True


def signal_handler(sig, frame):
    global running
    print("\n⏹  Shutting down...")
    running = False


signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)


# ── Serial (Arduino) ───────────────────────────────────────────────────────

class ArduinoSerial:
    """Thin wrapper around pyserial for the Phase-1 Arduino."""

    def __init__(self, port: str, baud: int = BAUD_RATE, dry_run: bool = False):
        self.dry_run = dry_run
        self.ser = None
        if not dry_run and serial is not None:
            try:
                self.ser = serial.Serial(port, baud, timeout=1)
                time.sleep(2)  # Arduino resets on serial open
                print(f"   ✅ Arduino connected on {port} @ {baud}")
            except Exception as e:
                print(f"   ⚠️  Arduino serial failed: {e}")
                print(f"   ⚠️  Falling back to dry-run mode")
                self.dry_run = True
        else:
            print(f"   🔇 Dry-run mode — no serial output")

    def send(self, char: str):
        """Send a single command character to the Arduino."""
        if self.dry_run:
            print(f"   [DRY-RUN] → Arduino: '{char}'")
            return
        try:
            self.ser.write(char.encode())
            self.ser.flush()
            print(f"   → Arduino: '{char}'")
        except Exception as e:
            print(f"   ❌ Serial write error: {e}")

    def close(self):
        if self.ser and self.ser.is_open:
            self.ser.close()


# ── Command Router ─────────────────────────────────────────────────────────

def handle_command(data: dict, arduino: ArduinoSerial) -> dict:
    """
    Process a single JSON command from the phone.
    Returns a response dict to send back.
    """
    cmd = data.get("cmd", "")

    if cmd == "move":
        direction = data.get("dir", "stop").lower()
        char = DIR_MAP.get(direction, "S")
        arduino.send(char)
        return {"type": "ack", "cmd": "move", "dir": direction, "ok": True}

    elif cmd == "ping":
        return {"type": "ack", "cmd": "ping", "ok": True}

    elif cmd == "mode":
        mode = data.get("value", "rc")
        print(f"   📡 Mode switch requested: {mode}")
        return {"type": "ack", "cmd": "mode", "value": mode, "ok": True}

    else:
        # Handle DPad format: {"type": "remote", "direction": "forward"}
        if data.get("type") == "remote":
            direction = data.get("direction", "stop").lower()
            char = DIR_MAP.get(direction, "S")
            arduino.send(char)
            return {"type": "ack", "cmd": "move", "dir": direction, "ok": True}

        print(f"   ❓ Unknown command: {data}")
        return {"type": "error", "msg": f"Unknown command: {cmd}"}


# ── Main Server Loop ──────────────────────────────────────────────────────

def run_server(arduino: ArduinoSerial, channel: int = RFCOMM_CHANNEL):
    """
    Listen for RFCOMM connections using native Python Bluetooth sockets.
    Accepts one client at a time, reconnects when client drops.
    """
    # AF_BLUETOOTH = 31 on Linux, BTPROTO_RFCOMM = 3
    server_sock = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_STREAM, socket.BTPROTO_RFCOMM)
    server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_sock.bind(("00:00:00:00:00:00", channel))
    server_sock.listen(1)
    server_sock.settimeout(2.0)

    print(f"\n{'═' * 50}")
    print(f"   🚗 Buggy BT Server (native RFCOMM)")
    print(f"   Channel: {channel}")
    print(f"   Waiting for Android client...")
    print(f"   (Make sure you ran: sudo sdptool add SP)")
    print(f"   (Make sure you ran: sudo hciconfig hci0 piscan)")
    print(f"{'═' * 50}\n")

    while running:
        client_sock = None
        try:
            # Accept blocks until a client connects (with 2s timeout)
            try:
                client_sock, client_info = server_sock.accept()
            except socket.timeout:
                continue  # loop back and check `running`
            except OSError as e:
                if not running:
                    break
                print(f"   ⚠️  Accept error: {e}")
                time.sleep(1)
                continue

            print(f"   📱 Client connected: {client_info}")
            client_sock.settimeout(2.0)
            buffer = ""

            while running:
                try:
                    data = client_sock.recv(1024)
                    if not data:
                        print(f"   📱 Client disconnected (empty read)")
                        break

                    buffer += data.decode("utf-8", errors="replace")

                    # Process all complete lines (commands are newline-delimited)
                    while "\n" in buffer:
                        line, buffer = buffer.split("\n", 1)
                        line = line.strip()
                        if not line:
                            continue

                        try:
                            cmd = json.loads(line)
                            print(f"   ← Phone: {cmd}")
                            response = handle_command(cmd, arduino)
                            reply = json.dumps(response) + "\n"
                            client_sock.send(reply.encode("utf-8"))
                            print(f"   → Phone: {response}")
                        except json.JSONDecodeError:
                            print(f"   ⚠️  Bad JSON: {line}")

                except socket.timeout:
                    continue  # no data — loop back
                except (OSError, ConnectionResetError) as e:
                    print(f"   📱 Client connection lost: {e}")
                    break

        except Exception as e:
            print(f"   ❌ Server error: {e}")

        finally:
            if client_sock:
                try:
                    client_sock.close()
                except Exception:
                    pass
            # Stop motors when client disconnects
            arduino.send("S")
            print(f"   ⏸  Motors stopped. Waiting for next client...\n")

    # Cleanup
    server_sock.close()
    arduino.close()
    print("   👋 Server shut down cleanly.")


# ── Entry Point ────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Buggy Bluetooth SPP Server")
    parser.add_argument(
        "--port", default=DEFAULT_SERIAL_PORT,
        help=f"Arduino serial port (default: {DEFAULT_SERIAL_PORT})"
    )
    parser.add_argument(
        "--baud", type=int, default=BAUD_RATE,
        help=f"Serial baud rate (default: {BAUD_RATE})"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Log commands without sending to Arduino"
    )
    parser.add_argument(
        "--channel", type=int, default=RFCOMM_CHANNEL,
        help=f"RFCOMM channel (default: {RFCOMM_CHANNEL})"
    )
    args = parser.parse_args()

    print(f"\n   🔧 Initializing...")
    arduino = ArduinoSerial(args.port, args.baud, dry_run=args.dry_run)
    run_server(arduino, channel=args.channel)


if __name__ == "__main__":
    main()
