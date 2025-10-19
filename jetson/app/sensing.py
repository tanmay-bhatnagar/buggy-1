import time
from .utils import median


class SensingOrchestrator:
    def __init__(self, cfg, link):
        self._link = link
        cadence = cfg.get("cadence_ms", {})
        self._rescan_ms = int(cadence.get("rescan_ms", 200))
        self._servo_settle_ms = int(cadence.get("servo_settle_ms", 100))
        self._meas_cooldown_ms = int(cadence.get("meas_cooldown_ms", 40))

        sweep = cfg.get("sweep", {})
        center_trim = int(sweep.get("center_trim_deg", 0))
        self._left_deg = int(sweep.get("left_deg", 135))
        self._right_deg = int(sweep.get("right_deg", 45))
        self._center_deg = 90 + center_trim
        self._step_deg = int(sweep.get("step_deg", 15))
        self._samples_per_point = int(sweep.get("samples_per_point", 3))

        # Build an interleaved sweep: center, center - step, center + step, ...
        self._angles_cycle = self._build_angles_cycle()
        self._cycle_index = 0

        self._last_scan_ms = 0
        self._last_ping_ms = 0
        self._servo_move_ms = 0
        self._samples = []
        self._awaiting_ping = False
        self._current_servo_deg = self._center_deg
        self._attempts = 0
        self._max_attempts_per_point = max(2, self._samples_per_point * 2)

        self._dist_center = float("nan")
        self._dist_left = float("nan")
        self._dist_right = float("nan")
        self._last_valid_center_ms = 0
        self._last_valid_left_ms = 0
        self._last_valid_right_ms = 0

    def _now_ms(self) -> int:
        return int(time.time() * 1000)

    def get_distances(self):
        return self._dist_left, self._dist_center, self._dist_right

    def get_servo_deg(self) -> int:
        return self._current_servo_deg

    def _build_angles_cycle(self):
        # Interleave right and left steps from center, respecting bounds
        angles = [self._center_deg]
        k = 1
        while True:
            changed = False
            right = self._center_deg - k * self._step_deg
            left = self._center_deg + k * self._step_deg
            if right >= self._right_deg:
                angles.append(right)
                changed = True
            if left <= self._left_deg:
                angles.append(left)
                changed = True
            if not changed:
                break
            k += 1
        return angles

    def _send_servo(self, deg: int):
        self._link.send_command(f"SERVO,{deg}")
        self._servo_move_ms = self._now_ms()
        self._awaiting_ping = False
        self._samples = []
        self._current_servo_deg = deg
        self._attempts = 0

    def _send_ping(self):
        self._link.send_command("PING")
        self._awaiting_ping = True
        self._last_ping_ms = self._now_ms()
        self._attempts += 1

    def _consume_lines(self):
        # Consume available serial lines, capture distance responses
        while True:
            line = self._link.read_line()
            if not line:
                break
            if line.startswith("DIST,"):
                parts = line.split(",", 1)
                if len(parts) == 2 and parts[1] != "NA":
                    try:
                        cm = float(parts[1])
                        self._samples.append(cm)
                    except ValueError:
                        pass
                # We received a reply for the last PING
                self._awaiting_ping = False
            # Ignore other lines here (STAT/OK/ERR)

    def tick(self):
        now = self._now_ms()
        # If time to scan a new point
        if now - self._last_scan_ms >= self._rescan_ms and not self._awaiting_ping and not self._samples:
            target = self._angles_cycle[self._cycle_index]
            self._send_servo(target)
            self._last_scan_ms = now
            return

        # After servo settle, start pinging until we collect samples_per_point
        if (self._servo_move_ms > 0 and now - self._servo_move_ms >= self._servo_settle_ms):
            if len(self._samples) < self._samples_per_point and not self._awaiting_ping:
                # Respect measurement cooldown between pings; stop after too many attempts
                if self._attempts >= self._max_attempts_per_point:
                    # Give up on this angle for now; advance with NaN
                    angle = self._angles_cycle[self._cycle_index]
                    if angle == self._center_deg:
                        self._dist_center = float("nan")
                    elif angle == self._left_deg:
                        self._dist_left = float("nan")
                    elif angle == self._right_deg:
                        self._dist_right = float("nan")
                    self._cycle_index = (self._cycle_index + 1) % len(self._angles_cycle)
                    self._servo_move_ms = 0
                    self._awaiting_ping = False
                    self._samples = []
                    self._attempts = 0
                elif len(self._samples) == 0 or (now - self._last_ping_ms >= self._meas_cooldown_ms):
                    self._send_ping()

        # Read any incoming distance lines
        self._consume_lines()

        # If we have enough samples, update the corresponding slot and advance
        if len(self._samples) >= self._samples_per_point:
            m = median(self._samples)
            angle = self._angles_cycle[self._cycle_index]
            if angle == self._center_deg:
                self._dist_center = m
                self._last_valid_center_ms = now
            elif angle == self._left_deg:
                self._dist_left = m
                self._last_valid_left_ms = now
            elif angle == self._right_deg:
                self._dist_right = m
                self._last_valid_right_ms = now
            # Advance cycle
            self._cycle_index = (self._cycle_index + 1) % len(self._angles_cycle)
            self._servo_move_ms = 0
            self._awaiting_ping = False
            self._samples = []
            self._attempts = 0

    def get_last_valid_center_ms(self) -> int:
        return self._last_valid_center_ms
