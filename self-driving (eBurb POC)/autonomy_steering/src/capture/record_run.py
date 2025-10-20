import argparse
import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List

import cv2

from src.arduino.label_reader import ArduinoLabelReader, LabelPacket
from src.capture.multi_cam_capture import FramePacket, MultiCameraCapture
from src.utils.config import ensure_dir, load_yaml
from src.utils.logging import get_logger, log_event
from src.utils.time import now_ns


def _run_id_from_format(fmt: str) -> str:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return fmt.replace("YYYYMMDD_HHMMSS", timestamp)


def _open_writers(output_dir: Path, config: dict) -> Dict[int, cv2.VideoWriter]:
    cams_cfg = config["cameras"]
    width = cams_cfg["resolution"]["width"]
    height = cams_cfg["resolution"]["height"]
    fps = cams_cfg["fps_target"]
    fourcc = cv2.VideoWriter_fourcc(*cams_cfg.get("fourcc", "MJPG"))

    writers: Dict[int, cv2.VideoWriter] = {}
    for cam_id in cams_cfg["device_indices"]:
        path = output_dir / f"cam{cam_id}.mp4"
        writer = cv2.VideoWriter(str(path), fourcc, fps, (width, height))
        if not writer.isOpened():
            raise RuntimeError(f"Failed to open writer for {path}")
        writers[cam_id] = writer
    return writers


def record_run(system_cfg_path: str, duration_s: float = 0.0) -> None:
    cfg = load_yaml(system_cfg_path)
    logger = get_logger("RunRecorder")
    run_id = _run_id_from_format(cfg["run"]["run_id_format"])
    output_root = Path(cfg["run"]["output_root"])
    output_dir = output_root / run_id
    ensure_dir(str(output_dir))

    capture = MultiCameraCapture(cfg)
    capture.open_cameras()

    label_cfg = cfg["arduino_serial"]
    label_reader = ArduinoLabelReader(label_cfg["port"], label_cfg["baud"])
    label_reader.connect()

    writers = _open_writers(output_dir, cfg)
    labels: List[LabelPacket] = []
    start_ns = now_ns()

    log_event(logger, "record", "start", run_id=run_id)
    try:
        while True:
            packets = capture.read_frames()
            for cam_id, packet in packets.items():
                writers[cam_id].write(packet.frame_bgr)

            label = label_reader.read_label_frame()
            if label:
                labels.append(label)

            if duration_s > 0:
                elapsed_s = (now_ns() - start_ns) / 1e9
                if elapsed_s >= duration_s:
                    break
    except KeyboardInterrupt:
        log_event(logger, "record", "stopped_by_user", run_id=run_id)
    finally:
        capture.close()
        label_reader.close()
        for writer in writers.values():
            writer.release()

    labels_path = output_dir / "labels.csv"
    with open(labels_path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "t_us_arduino",
                "t_ns_host",
                "enc_counts",
                "steer_angle_deg",
                "killswitch_ok",
                "seq",
            ]
        )
        for label in labels:
            writer.writerow(
                [
                    label.t_us_arduino,
                    label.t_ns_host,
                    label.enc_counts,
                    label.steer_angle_deg,
                    int(label.killswitch_ok),
                    label.seq,
                ]
            )

    manifest = {
        "run_id": run_id,
        "output_dir": str(output_dir),
        "num_labels": len(labels),
        "camera_ids": cfg["cameras"]["device_indices"],
        "fps_target": cfg["cameras"]["fps_target"],
        "created_at": datetime.now().isoformat(),
    }
    with open(output_dir / "manifest.json", "w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2)

    log_event(logger, "record", "complete", run_id=run_id, num_labels=len(labels))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--duration_s", type=float, default=0.0)
    args = parser.parse_args()
    record_run(args.config, args.duration_s)


if __name__ == "__main__":
    main()
