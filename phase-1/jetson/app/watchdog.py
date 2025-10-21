import time


class Watchdog:
    def __init__(self, cfg, link):
        self._hb_period = float(cfg.get("watchdog", {}).get("hb_period_ms", 200)) / 1000.0
        self._link = link
        self._last_hb = 0.0

    def tick(self):
        now = time.time()
        if now - self._last_hb >= self._hb_period:
            self._link.send_command("HB")
            self._last_hb = now
