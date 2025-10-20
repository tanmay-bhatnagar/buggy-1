#!/usr/bin/env python3
import sys, time, threading, select, termios, tty
import serial

PORT_CANDIDATES = ["/dev/ttyACM0","/dev/ttyACM1","/dev/ttyUSB0"]
BAUD = 115200

HELP = """
Commands:
  forward <secs>
  back <secs>
  left <secs>          in-place CCW
  right <secs>         in-place CW
  spin_cw <secs>
  spin_ccw <secs>
  stop <secs>          (STOP just brakes; use 'a' to abort mid-run)
  ultrasound on <secs> [spin on|off]
  diag
  abort                (from prompt)
  quit / exit

While a command is RUNNING:
  Press 'a' to ABORT immediately.
"""

MOVE = {
    "forward": "FWD",
    "back": "BACK",
    "left": "LEFT",
    "right": "RIGHT",
    "spin_cw": "SPIN_CW",
    "spin_ccw": "SPIN_CCW",
    "stop": "STOP",
}

class Link:
    def __init__(self, port):
        self.ser = serial.Serial(port, BAUD, timeout=0.1)
        self._unlock = threading.Event(); self._unlock.set()
        t = threading.Thread(target=self._reader, daemon=True); t.start()

    def _reader(self):
        buf = b""
        while True:
            chunk = self.ser.read(512)
            if chunk:
                buf += chunk
                while b"\n" in buf:
                    line, buf = buf.split(b"\n", 1)
                    s = line.decode("utf-8", errors="ignore").rstrip()
                    if s:
                        print(s)
                        if s.startswith("EVENT COMPLETE") or s == "EVENT ABORTED":
                            self._unlock.set()
            else:
                time.sleep(0.02)

    def send(self, s: str):
        self.ser.write((s.strip()+"\n").encode("utf-8"))

    def run_blocking(self, line: str):
        # Send and block until Arduino prints COMPLETE/ABORTED.
        self._unlock.clear()
        self.send(line)
        # raw mode so we can catch single-key 'a'
        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        try:
            tty.setcbreak(fd)
            while not self._unlock.is_set():
                # poll stdin for a single key
                r, _, _ = select.select([sys.stdin], [], [], 0.05)
                if r:
                    ch = sys.stdin.read(1)
                    if ch in ('a','A'):
                        self.send("ABORT")
                # otherwise just loop while the reader thread waits for COMPLETE/ABORTED
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)

def autodetect_port():
    for p in PORT_CANDIDATES:
        try:
            s = serial.Serial(p, BAUD, timeout=0.1); s.close(); return p
        except: pass
    print("No Arduino port found. Use: ./terminal.py /dev/ttyACM0"); sys.exit(1)

def build_move(cmd, args):
    if len(args) < 1: print("Need <secs>"); return None
    try: secs = float(args[0])
    except: print("Bad seconds"); return None
    return f"MOVE {MOVE[cmd]} {secs:.3f}"

def build_ultra(args):
    if len(args) < 2: print("Usage: ultrasound on <secs> [spin on|off]"); return None
    onoff = args[0].lower()
    try: secs = float(args[1])
    except: print("Bad seconds"); return None
    spin = False
    if len(args) >= 4 and args[2].lower()=="spin":
        spin = args[3].lower() in ("on","1","true","yes")
    return f"ULTRASONIC {onoff.upper()} {secs:.3f} SPIN {'ON' if spin else 'OFF'}"

def main():
    port = sys.argv[1] if len(sys.argv)>1 else autodetect_port()
    print(f"[info] Opening {port} @ {BAUD}")
    link = Link(port)
    print(HELP.strip())
    while True:
        try: line = input("buggy> ").strip()
        except KeyboardInterrupt: print(); continue
        if not line: continue
        low = line.lower()
        if low in ("quit","exit"): print("bye."); break
        if low == "help": print(HELP.strip()); continue
        if low == "abort": link.run_blocking("ABORT"); continue
        if low == "diag": link.run_blocking("DIAG"); continue

        toks = low.split()
        cmd, args = toks[0], toks[1:]
        if cmd in MOVE: out = build_move(cmd, args)
        elif cmd == "ultrasound": out = build_ultra(args)
        else: print("Unknown command. Type 'help'."); continue
        if out: link.run_blocking(out)

if __name__ == "__main__":
    main()

