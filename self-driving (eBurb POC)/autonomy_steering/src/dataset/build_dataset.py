import argparse
import csv
import json
from pathlib import Path
from typing import List, Tuple

import cv2
import numpy as np
import tensorflow as tf
from tqdm import tqdm

from src.preprocess.preprocess_ops import preprocess_frame
from src.utils.config import ensure_dir, load_yaml, save_json
from src.utils.logging import get_logger, log_event


def _load_labels(labels_path: Path) -> List[dict]:
    labels = []
    with open(labels_path, "r", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            labels.append(
                {
                    "t_ns_host": int(row["t_ns_host"]),
                    "enc_counts": int(row["enc_counts"]),
                    "steer_angle_deg": float(row["steer_angle_deg"]),
                }
            )
    labels.sort(key=lambda x: x["t_ns_host"])
    return labels


def _interpolate_label(labels: List[dict], t_ns: int) -> float:
    if not labels:
        raise ValueError("No labels available for interpolation.")
    if t_ns <= labels[0]["t_ns_host"]:
        return labels[0]["steer_angle_deg"]
    if t_ns >= labels[-1]["t_ns_host"]:
        return labels[-1]["steer_angle_deg"]

    for idx in range(1, len(labels)):
        prev = labels[idx - 1]
        curr = labels[idx]
        if prev["t_ns_host"] <= t_ns <= curr["t_ns_host"]:
            t0 = prev["t_ns_host"]
            t1 = curr["t_ns_host"]
            alpha = (t_ns - t0) / max((t1 - t0), 1)
            return float(prev["steer_angle_deg"] + alpha * (curr["steer_angle_deg"] - prev["steer_angle_deg"]))
    return labels[-1]["steer_angle_deg"]


def _serialize_example(image: np.ndarray, label: float) -> bytes:
    feature = {
        "image": tf.train.Feature(bytes_list=tf.train.BytesList(value=[image.tobytes()])),
        "label": tf.train.Feature(float_list=tf.train.FloatList(value=[label])),
        "shape": tf.train.Feature(int64_list=tf.train.Int64List(value=list(image.shape))),
    }
    example = tf.train.Example(features=tf.train.Features(feature=feature))
    return example.SerializeToString()


def _split_runs(runs: List[str]) -> Tuple[List[str], List[str], List[str]]:
    if not runs:
        return [], [], []
    if len(runs) == 1:
        return runs, [], []
    train_end = max(1, int(len(runs) * 0.7))
    val_end = max(train_end + 1, int(len(runs) * 0.85))
    train_runs = runs[:train_end]
    val_runs = runs[train_end:val_end]
    test_runs = runs[val_end:]
    return train_runs, val_runs, test_runs


def build_dataset(system_cfg: str, model_cfg: str, out_id: str, runs: List[str]) -> None:
    system = load_yaml(system_cfg)
    model = load_yaml(model_cfg)
    logger = get_logger("DatasetBuilder")

    output_dir = Path("data/processed") / out_id
    ensure_dir(str(output_dir))

    train_runs, val_runs, test_runs = _split_runs(sorted(runs))
    writers = {
        "train": tf.io.TFRecordWriter(str(output_dir / "train.tfrecord")),
        "val": tf.io.TFRecordWriter(str(output_dir / "val.tfrecord")),
        "test": tf.io.TFRecordWriter(str(output_dir / "test.tfrecord")),
    }

    stats = {"train": 0, "val": 0, "test": 0}
    for run_id in runs:
        split = "train" if run_id in train_runs else "val" if run_id in val_runs else "test"
        writer = writers[split]
        run_dir = Path(system["run"]["output_root"]) / run_id
        labels_path = run_dir / "labels.csv"
        video_path = run_dir / f"cam{model['input']['use_camera']}.mp4"
        if not labels_path.exists() or not video_path.exists():
            log_event(logger, "dataset", "missing_run_files", run_id=run_id)
            continue

            labels = _load_labels(labels_path)
            cap = cv2.VideoCapture(str(video_path))
            fps = cap.get(cv2.CAP_PROP_FPS) or system["cameras"]["fps_target"]
            frame_idx = 0

            pbar = tqdm(total=int(cap.get(cv2.CAP_PROP_FRAME_COUNT)), desc=f"run {run_id}")
            while True:
                ok, frame = cap.read()
                if not ok or frame is None:
                    break
                t_ns = int(frame_idx / fps * 1e9)
                label = _interpolate_label(labels, labels[0]["t_ns_host"] + t_ns)
                processed, _ = preprocess_frame(frame, model)
                writer.write(_serialize_example(processed, label))
                frame_idx += 1
                stats[split] += 1
                pbar.update(1)
            pbar.close()
            cap.release()

    for writer in writers.values():
        writer.close()

    dataset_stats = {
        "dataset_id": out_id,
        "train_samples": stats["train"],
        "val_samples": stats["val"],
        "test_samples": stats["test"],
        "train_runs": train_runs,
        "val_runs": val_runs,
        "test_runs": test_runs,
    }
    save_json(f"artifacts/reports/{out_id}_dataset_stats.json", dataset_stats)
    log_event(
        logger,
        "dataset",
        "complete",
        dataset_id=out_id,
        train_samples=stats["train"],
        val_samples=stats["val"],
        test_samples=stats["test"],
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--system", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--out_id", required=True)
    parser.add_argument("--runs", nargs="+", default=[])
    args = parser.parse_args()

    system = load_yaml(args.system)
    runs = args.runs
    if not runs:
        output_root = Path(system["run"]["output_root"])
        runs = [p.name for p in output_root.iterdir() if p.is_dir()]
    build_dataset(args.system, args.model, args.out_id, runs)


if __name__ == "__main__":
    main()
