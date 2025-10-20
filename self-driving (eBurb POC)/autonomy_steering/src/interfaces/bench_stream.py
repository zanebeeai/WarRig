import argparse
import csv
import json
import time
from pathlib import Path
from threading import Event, Thread
from typing import Optional

import serial
from src.utils.config import load_yaml
from src.utils.logging import get_logger, log_event
from src.utils.time import now_ms


class BenchSerialStreamer:
    def __init__(self, system_cfg: dict, port: str, baud: int):
        self.system_cfg = system_cfg
        self.port = port
        self.baud = baud
        self.serial: Optional[serial.Serial] = None
        self.logger = get_logger("BenchStream")
        self.stop_event = Event()
        self.last_killswitch_ms: Optional[int] = None
        self.arm_deadline_ms: Optional[int] = None

    def connect(self) -> None:
        self.serial = serial.Serial(self.port, self.baud, timeout=1.0)
        log_event(self.logger, "bench", "connected", port=self.port, baud=self.baud)

    def start_label_monitor(self) -> None:
        def _loop() -> None:
            while not self.stop_event.is_set():
                if self.serial is None:
                    continue
                line = self.serial.readline().decode("utf-8", errors="ignore").strip()
                if not line:
                    continue
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if payload.get("killswitch_ok"):
                    self.last_killswitch_ms = now_ms()
        Thread(target=_loop, daemon=True).start()

    def arm(self) -> str:
        token = f"ARM{int(time.time())}"
        timeout_s = float(self.system_cfg["safety"]["arm_timeout_s"])
        self.arm_deadline_ms = now_ms() + int(timeout_s * 1000)
        return token

    def _check_safety(self) -> None:
        if self.arm_deadline_ms is None or now_ms() > self.arm_deadline_ms:
            raise RuntimeError("Arm token expired.")
        if self.system_cfg["safety"]["killswitch_required"]:
            if self.last_killswitch_ms is None:
                raise RuntimeError("No killswitch heartbeat yet.")
            max_gap_ms = int(1000 / max(self.system_cfg["safety"]["heartbeat_hz"], 1))
            if now_ms() - self.last_killswitch_ms > max_gap_ms * 2:
                raise RuntimeError("Killswitch heartbeat timeout.")

    def send_command(self, theta_cmd: float, token: str, seq: int) -> None:
        if self.serial is None:
            raise RuntimeError("Serial not connected.")
        self._check_safety()
        payload = {
            "t_ms_host": now_ms(),
            "theta_cmd": float(theta_cmd),
            "mode": "bench",
            "arm_token": token,
            "seq": seq,
        }
        message = json.dumps(payload) + "\n"
        self.serial.write(message.encode("utf-8"))

    def close(self) -> None:
        self.stop_event.set()
        if self.serial:
            self.serial.close()
            self.serial = None


def stream_from_csv(system_cfg: str, commands_csv: str, bench_mode: bool, arm: bool) -> None:
    if not bench_mode:
        raise RuntimeError("Bench mode is required for steering actuation.")
    if not arm:
        raise RuntimeError("Arm flag is required to stream commands.")

    cfg = load_yaml(system_cfg)
    serial_cfg = cfg["arduino_serial"]
    streamer = BenchSerialStreamer(cfg, serial_cfg["port"], serial_cfg["baud"])
    streamer.connect()
    streamer.start_label_monitor()

    token = streamer.arm()
    log_event(streamer.logger, "bench", "armed", token=token)

    rate_hz = cfg["arduino_serial"]["label_hz"]
    interval_s = 1.0 / max(rate_hz, 1)
    seq = 0

    with open(commands_csv, "r", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            theta_cmd = float(row.get("theta_cmd", row.get("theta_pred", 0.0)))
            streamer.send_command(theta_cmd, token, seq)
            seq += 1
            time.sleep(interval_s)

    streamer.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--system", required=True)
    parser.add_argument("--commands_csv", required=True)
    parser.add_argument("--bench_mode", action="store_true")
    parser.add_argument("--arm", action="store_true")
    args = parser.parse_args()

    stream_from_csv(args.system, args.commands_csv, args.bench_mode, args.arm)


if __name__ == "__main__":
    main()
