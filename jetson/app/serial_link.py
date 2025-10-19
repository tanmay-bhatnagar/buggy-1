import serial
import time
from typing import Optional


class SerialLink:
    def __init__(self, cfg):
        self._port = cfg["serial"]["port"]
        self._baud = int(cfg["serial"]["baud"])
        self._timeout = float(cfg["serial"]["timeout_ms"]) / 1000.0
        self._ser: Optional[serial.Serial] = None
        self._last_send = 0.0
        self._connect()

    def _connect(self):
        try:
            self._ser = serial.Serial(
                self._port,
                self._baud,
                timeout=self._timeout,
                write_timeout=self._timeout,
            )
            time.sleep(0.2)
            self._ser.reset_input_buffer()
            self._ser.reset_output_buffer()
        except Exception:
            self._ser = None

    def send_command(self, line: str):
        payload = (line.strip() + "\n").encode("utf-8")
        if not self._ser:
            # try reconnect
            time.sleep(0.5)
            self._connect()
        try:
            if self._ser:
                self._ser.write(payload)
                self._ser.flush()
                self._last_send = time.time()
        except Exception:
            # attempt reconnect once
            try:
                if self._ser:
                    self._ser.close()
            except Exception:
                pass
            self._ser = None
            time.sleep(0.5)
            self._connect()
            try:
                if self._ser:
                    self._ser.write(payload)
                    self._ser.flush()
                    self._last_send = time.time()
            except Exception:
                pass

    def read_line(self) -> Optional[str]:
        if not self._ser:
            time.sleep(0.5)
            self._connect()
        try:
            raw = self._ser.readline() if self._ser else b""
            if not raw:
                return None
            return raw.decode("utf-8", errors="ignore").strip()
        except Exception:
            # reconnect and give up this cycle
            try:
                if self._ser:
                    self._ser.close()
            except Exception:
                pass
            self._ser = None
            time.sleep(0.5)
            self._connect()
            return None

    @property
    def last_send_time(self) -> float:
        return self._last_send
