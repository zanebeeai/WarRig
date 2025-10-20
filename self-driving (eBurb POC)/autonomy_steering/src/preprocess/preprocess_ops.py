from typing import Dict, Tuple

import cv2
import numpy as np


def _apply_roi(frame: np.ndarray, roi: list) -> np.ndarray:
    if not roi or len(roi) != 4:
        return frame
    x, y, w, h = roi
    return frame[y : y + h, x : x + w]


def _apply_warp(frame: np.ndarray, cfg: dict) -> np.ndarray:
    warp_cfg = cfg.get("perspective_warp", {})
    if not warp_cfg.get("enabled", False):
        return frame
    src_pts = np.array(warp_cfg.get("src_points", []), dtype=np.float32)
    dst_pts = np.array(warp_cfg.get("dst_points", []), dtype=np.float32)
    if src_pts.size == 0 or dst_pts.size == 0:
        return frame
    height, width = frame.shape[:2]
    matrix = cv2.getPerspectiveTransform(src_pts, dst_pts)
    return cv2.warpPerspective(frame, matrix, (width, height))


def preprocess_frame(frame_bgr: np.ndarray, model_cfg: dict) -> Tuple[np.ndarray, Dict[str, np.ndarray]]:
    debug: Dict[str, np.ndarray] = {}
    frame = _apply_roi(frame_bgr, model_cfg["input"].get("roi", []))
    debug["roi"] = frame.copy()

    preprocess_cfg = model_cfg.get("preprocess", {})
    colorspace = preprocess_cfg.get("colorspace", "gray")
    if colorspace == "gray":
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    else:
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    debug["colorspace"] = frame.copy()

    frame = _apply_warp(frame, preprocess_cfg)
    debug["warp"] = frame.copy()

    canny_cfg = preprocess_cfg.get("canny", {})
    if canny_cfg.get("enabled", False):
        low = int(canny_cfg.get("low", 50))
        high = int(canny_cfg.get("high", 150))
        frame = cv2.Canny(frame, low, high)
    debug["canny"] = frame.copy()

    resize_h, resize_w = model_cfg["input"]["resize_hw"]
    frame = cv2.resize(frame, (resize_w, resize_h))
    debug["resize"] = frame.copy()

    if model_cfg["input"]["channels"] == 1 and frame.ndim == 2:
        frame = frame[:, :, None]

    frame = frame.astype(np.float32)
    norm = model_cfg["input"].get("normalize", "0_1")
    if norm == "0_1":
        frame /= 255.0
    elif norm == "-1_1":
        frame = frame / 127.5 - 1.0
    elif norm == "zscore":
        mean = frame.mean()
        std = frame.std() or 1.0
        frame = (frame - mean) / std

    return frame, debug


def visualize_debug(frame_bgr: np.ndarray, intermediates: Dict[str, np.ndarray]) -> np.ndarray:
    overlay = frame_bgr.copy()
    if "canny" in intermediates:
        canny = intermediates["canny"]
        if canny.ndim == 2:
            canny = cv2.cvtColor(canny, cv2.COLOR_GRAY2BGR)
        overlay = cv2.addWeighted(overlay, 0.8, canny, 0.2, 0)
    return overlay
