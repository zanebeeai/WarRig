import json
from dataclasses import dataclass
from typing import Optional

import serial

from src.utils.logging import get_logger, log_event
from src.utils.time import now_ns


@dataclass
class LabelPacket:
    t_us_arduino: int
    t_ns_host: int
    enc_counts: int
    steer_angle_deg: float
    killswitch_ok: bool
    seq: int


class ArduinoLabelReader:
    def __init__(self, port: str, baud: int):
        self.port = port
        self.baud = baud
        self.serial: Optional[serial.Serial] = None
        self.last_seq: Optional[int] = None
        self.logger = get_logger("ArduinoLabelReader")

    def connect(self) -> None:
        self.serial = serial.Serial(self.port, self.baud, timeout=1.0)
        log_event(self.logger, "arduino", "connected", port=self.port, baud=self.baud)

    def read_label_frame(self) -> Optional[LabelPacket]:
        if self.serial is None:
            raise RuntimeError("Serial not connected.")
        line = self.serial.readline().decode("utf-8", errors="ignore").strip()
        if not line:
            return None
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            log_event(self.logger, "arduino", "bad_json")
            return None

        required = {"t_us", "enc_counts", "steer_angle_deg", "killswitch_ok", "seq"}
        if not required.issubset(payload.keys()):
            log_event(self.logger, "arduino", "missing_fields", payload=payload)
            return None

        seq = int(payload["seq"])
        if self.last_seq is not None and seq <= self.last_seq:
            log_event(self.logger, "arduino", "seq_non_monotonic", seq=seq)
        self.last_seq = seq

        packet = LabelPacket(
            t_us_arduino=int(payload["t_us"]),
            t_ns_host=now_ns(),
            enc_counts=int(payload["enc_counts"]),
            steer_angle_deg=float(payload["steer_angle_deg"]),
            killswitch_ok=bool(payload["killswitch_ok"]),
            seq=seq,
        )
        return packet

    def close(self) -> None:
        if self.serial:
            self.serial.close()
            self.serial = None
