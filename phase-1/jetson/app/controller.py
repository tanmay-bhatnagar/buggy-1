import time
from dataclasses import dataclass
from .telemetry import TelemetryRow


@dataclass
class Hysteresis:
    slow_enter: float
    slow_exit: float
    turn_enter: float
    turn_exit: float
    stop_enter: float
    stop_exit: float


class ControlStateMachine:
    def __init__(self, cfg, link, sensing, telemetry):
        self._link = link
        self._sensing = sensing
        self._telemetry = telemetry

        thr = cfg.get("thresholds_cm", {})
        self._hyst = Hysteresis(
            slow_enter=thr.get("slow_enter", 60),
            slow_exit=thr.get("slow_exit", 75),
            turn_enter=thr.get("turn_enter", 35),
            turn_exit=thr.get("turn_exit", 45),
            stop_enter=thr.get("stop_enter", 20),
            stop_exit=thr.get("stop_exit", 30),
        )

        cadence = cfg.get("cadence_ms", {})
        self._min_turn_ms = int(cadence.get("min_turn_ms", 550))
        self._backoff_ms = int(cadence.get("backoff_ms", 500))
        self._rescan_ms = int(cadence.get("rescan_ms", 200))
        self._stall_timer_ms = int(cadence.get("stall_timer_ms", 2500))

        self._speed = "FAST"
        self._state = "CRUISE"
        self._commit_until_ms = 0
        self._backoff_until_ms = 0
        self._stall_start_ms = 0
        self._last_log_ms = 0
        self._last_cmd = ""

        self._telemetry.configure(cfg)

    def _now_ms(self) -> int:
        return int(time.time() * 1000)

    def _send_once(self, cmd: str):
        if cmd and cmd != self._last_cmd:
            self._link.send_command(cmd)
            self._last_cmd = cmd

    def _update_speed(self, dist_center: float):
        if self._speed == "FAST" and dist_center < self._hyst.slow_enter:
            self._speed = "SLOW"
        elif self._speed == "SLOW" and dist_center > self._hyst.slow_exit:
            self._speed = "FAST"

    def _decide_action(self, dl: float, dc: float, dr: float):
        now = self._now_ms()
        # Safety: backoff on immediate obstacle (only trigger once, don't retrigger)
        if dc < self._hyst.stop_enter and self._state != "BACKOFF":
            self._state = "BACKOFF"
            self._backoff_until_ms = now + self._backoff_ms
            return f"B,SLOW", "BACKOFF"

        # Commit window: hold current turn/spin for minimum time
        if self._state in ("AVOID_ARC", "AVOID_SPIN") and now < self._commit_until_ms:
            # Keep previous command
            return self._last_cmd, self._state

        # Normal cruise vs avoid
        if dc < self._hyst.turn_enter:
            # Choose wider side
            if dl > dr:
                self._state = "AVOID_ARC"
                self._commit_until_ms = now + self._min_turn_ms
                return "L,SLOW", "AVOID_ARC"
            else:
                self._state = "AVOID_ARC"
                self._commit_until_ms = now + self._min_turn_ms
                return "R,SLOW", "AVOID_ARC"
        elif dc > self._hyst.turn_exit:
            self._state = "CRUISE"
            return f"F,{self._speed}", "CRUISE"

        # Default gentle forward
        return f"F,{self._speed}", "CRUISE"

    def tick(self):
        dl, dc, dr = self._sensing.get_distances()
        # Substitute large distance if NaN
        if not (dc == dc):
            dc = 999.0
        if not (dl == dl):
            dl = 999.0
        if not (dr == dr):
            dr = 999.0

        self._update_speed(dc)

        now = self._now_ms()
        decision = ""
        cmd = ""

        # Sensor recovery: if center has been invalid for a while, crawl SLOW and keep scanning
        if self._sensing.get_last_valid_center_ms() == 0 or now - self._sensing.get_last_valid_center_ms() > (self._rescan_ms * 3):
            self._state = "SENSOR_RECOVERY"
            cmd = "F,SLOW"
            decision = "SENSOR_RECOVERY"

        if self._state == "BACKOFF" and not cmd:
            if now < self._backoff_until_ms:
                cmd = "B,SLOW"
                decision = "BACKOFF"
            else:
                # After backoff, do a spin burst toward wider side
                if dl > dr:
                    self._state = "AVOID_SPIN"
                    self._commit_until_ms = now + self._min_turn_ms
                    cmd = "SPINL"
                    decision = "AVOID_SPIN"
                else:
                    self._state = "AVOID_SPIN"
                    self._commit_until_ms = now + self._min_turn_ms
                    cmd = "SPINR"
                    decision = "AVOID_SPIN"

        if not cmd:
            cmd, decision = self._decide_action(dl, dc, dr)

        # Stall detection: if scene doesn't improve, do backoff then spin (per README)
        if self._state not in ("BACKOFF",):
            if dc < self._hyst.turn_exit:
                if self._stall_start_ms == 0:
                    self._stall_start_ms = now
                elif now - self._stall_start_ms > self._stall_timer_ms and now >= self._commit_until_ms:
                    self._state = "BACKOFF"
                    self._backoff_until_ms = now + self._backoff_ms
                    cmd = "B,SLOW"
                    decision = "STALL_BACKOFF"
            else:
                self._stall_start_ms = 0

        self._send_once(cmd)

        if now - self._last_log_ms >= self._rescan_ms:
            row = TelemetryRow(
                t=time.time(),
                state=self._state,
                speed=self._speed,
                dist_center=dc,
                dist_left=dl,
                dist_right=dr,
                decision=decision,
                servo_deg=self._sensing.get_servo_deg(),
                cmd=cmd,
                latency_ms=0.0,
            )
            self._telemetry.log(row)
            self._last_log_ms = now
