#!/usr/bin/env python3
import time
import argparse
import serial


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--port", default="/dev/ttyACM0")
    p.add_argument("--baud", type=int, default=115200)
    p.add_argument("--seconds", type=int, default=3)
    p.add_argument("--echo", default=None, help="Send a one-time command like STOP")
    args = p.parse_args()

    ser = serial.Serial(args.port, args.baud, timeout=0.2, write_timeout=0.2)
    ser.reset_input_buffer()
    ser.reset_output_buffer()

    if args.echo:
        ser.write((args.echo.strip() + "\n").encode("utf-8"))
        ser.flush()

    t0 = time.time()
    while time.time() - t0 < args.seconds:
        ser.write(b"HB\n")
        ser.flush()
        line = ser.readline().decode("utf-8", errors="ignore").strip()
        if line and (line.startswith("DIST,") or line.startswith("STAT,")):
            print(line)
        time.sleep(0.05)

    try:
        ser.close()
    except Exception:
        pass


if __name__ == "__main__":
    main()
