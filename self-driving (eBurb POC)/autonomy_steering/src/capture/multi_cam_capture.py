from dataclasses import dataclass
from typing import Dict, List, Optional

import cv2
import numpy as np

from src.utils.logging import get_logger, log_event
from src.utils.time import now_ns


@dataclass
class FramePacket:
    t_ns: int
    frame_bgr: np.ndarray
    cam_id: int
    seq: int


class MultiCameraCapture:
    def __init__(self, config: dict):
        self.config = config
        self.logger = get_logger("MultiCameraCapture")
        self.captures: List[cv2.VideoCapture] = []
        self.seq: Dict[int, int] = {}
        self.opened = False

    def _backend_flag(self) -> int:
        backend = self.config["cameras"].get("backend", "CAP_ANY")
        return getattr(cv2, backend, cv2.CAP_ANY)

    def open_cameras(self) -> None:
        cams_cfg = self.config["cameras"]
        indices = cams_cfg["device_indices"]
        width = cams_cfg["resolution"]["width"]
        height = cams_cfg["resolution"]["height"]
        fps = cams_cfg["fps_target"]
        fourcc = cams_cfg.get("fourcc", "MJPG")
        backend_flag = self._backend_flag()

        self.captures = []
        self.seq = {}
        for cam_id in indices:
            cap = cv2.VideoCapture(cam_id, backend_flag)
            if not cap.isOpened():
                raise RuntimeError(f"Failed to open camera {cam_id}")
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
            cap.set(cv2.CAP_PROP_FPS, fps)
            cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*fourcc))
            self.captures.append(cap)
            self.seq[cam_id] = 0

            actual_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            actual_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            actual_fps = cap.get(cv2.CAP_PROP_FPS)
            log_event(
                self.logger,
                "capture",
                "camera_opened",
                cam_id=cam_id,
                width=actual_w,
                height=actual_h,
                fps=actual_fps,
                fourcc=fourcc,
            )

        self.opened = True

    def read_frames(self) -> Dict[int, FramePacket]:
        if not self.opened:
            raise RuntimeError("Cameras not opened.")

        packets: Dict[int, FramePacket] = {}
        for idx, cap in enumerate(self.captures):
            cam_id = self.config["cameras"]["device_indices"][idx]
            ok, frame = cap.read()
            if not ok or frame is None:
                log_event(self.logger, "capture", "frame_drop", cam_id=cam_id)
                continue
            t_ns = now_ns()
            seq = self.seq[cam_id]
            self.seq[cam_id] = seq + 1
            packets[cam_id] = FramePacket(
                t_ns=t_ns,
                frame_bgr=frame,
                cam_id=cam_id,
                seq=seq,
            )
        return packets

    def close(self) -> None:
        for cap in self.captures:
            cap.release()
        self.captures = []
        self.opened = False
