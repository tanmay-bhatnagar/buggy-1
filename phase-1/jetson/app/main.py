#!/usr/bin/env python3
import time
from .controller import ControlStateMachine
from .serial_link import SerialLink
from .sensing import SensingOrchestrator
from .telemetry import TelemetryLogger
from .config import load_config
from .watchdog import Watchdog
import sys


def run():
    cfg = load_config()
    telemetry = TelemetryLogger()
    link = SerialLink(cfg)
    sensing = SensingOrchestrator(cfg, link)
    sm = ControlStateMachine(cfg, link, sensing, telemetry)
    watchdog = Watchdog(cfg, link)

    try:
        # Pairing countdown (IDLE state)
        deadline = time.time() + max(0, int(cfg.get("pairing_seconds", 5)))
        while time.time() < deadline:
            # Still send heartbeats and read any serial noise
            watchdog.tick()
            _ = link.read_line()
            time.sleep(0.05)
        while True:
            watchdog.tick()
            sensing.tick()
            sm.tick()
            telemetry.tick()
            time.sleep(max(0.0, float(cfg.get("loop_sleep_s", 0.01))))
    except KeyboardInterrupt:
        link.send_command("STOP")
        telemetry.close()


if __name__ == "__main__":
    run()
