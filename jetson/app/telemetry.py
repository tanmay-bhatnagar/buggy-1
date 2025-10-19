import csv
import os
import time
from dataclasses import dataclass
from typing import Optional


@dataclass
class TelemetryRow:
    t: float
    state: str
    speed: str
    dist_center: float
    dist_left: float
    dist_right: float
    decision: str
    servo_deg: float
    cmd: str
    latency_ms: float


class TelemetryLogger:
    def __init__(self, path: Optional[str] = None):
        self._path = path
        self._file = None
        self._writer = None
        self._last_line_time = 0.0
        self._console_hud = False

    def configure(self, cfg):
        log_cfg = cfg.get("logging", {})
        path = self._path or log_cfg.get("csv_path", "logs/telemetry_phase1.csv")
        parent = os.path.dirname(path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        self._file = open(path, "w", newline="")
        self._writer = csv.writer(self._file)
        self._console_hud = bool(log_cfg.get("console_hud", True))
        self._writer.writerow([
            "t","state","speed","dist_center","dist_left","dist_right",
            "decision","servo_deg","cmd","latency_ms",
        ])

    def log(self, row: TelemetryRow):
        if not self._writer:
            return
        self._writer.writerow([
            row.t, row.state, row.speed, row.dist_center, row.dist_left,
            row.dist_right, row.decision, row.servo_deg, row.cmd, row.latency_ms
        ])
        self._last_line_time = time.time()
        if self._console_hud:
            print(f"{row.t:.2f} {row.state:<14} v={row.speed:<5} C/L/R="
                  f"{row.dist_center:.1f}/{row.dist_left:.1f}/{row.dist_right:.1f}"
                  f" servo={row.servo_deg:>3.0f} cmd={row.cmd:<8} dec={row.decision}")

    def tick(self):
        pass

    def close(self):
        if self._file:
            self._file.close()
            self._file = None
