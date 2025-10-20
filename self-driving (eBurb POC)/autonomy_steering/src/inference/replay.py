import argparse
import csv
import json
from pathlib import Path
from time import perf_counter

import cv2
import numpy as np
import tensorflow as tf

from src.inference.postprocess import PostprocessState, postprocess
from src.preprocess.preprocess_ops import preprocess_frame
from src.utils.config import ensure_dir, load_yaml
from src.utils.logging import get_logger, log_event


def replay(system_cfg: str, model_cfg: str, replay_cfg: str, run_id: str, exp_id: str) -> None:
    system = load_yaml(system_cfg)
    model = load_yaml(model_cfg)
    replay_cfg = load_yaml(replay_cfg)
    logger = get_logger("Replay")

    run_dir = Path(system["run"]["output_root"]) / run_id
    video_path = run_dir / f"cam{model['input']['use_camera']}.mp4"
    labels_path = run_dir / "labels.csv"

    export_path = Path("artifacts/exports") / exp_id / "saved_model"
    model_tf = tf.keras.models.load_model(str(export_path))

    cap = cv2.VideoCapture(str(video_path))
    fps = replay_cfg["timing"]["replay_fps"]
    frame_delay_ms = int(1000 / max(fps, 1))

    ensure_dir("artifacts/reports")
    overlay_path = Path("artifacts/reports") / f"{run_id}_overlay.mp4"
    out_writer = None

    commands_path = Path("artifacts/reports") / f"{run_id}_commands.csv"
    commands_handle = open(commands_path, "w", newline="", encoding="utf-8")
    command_writer = csv.writer(commands_handle)
    command_writer.writerow(["frame", "theta_pred", "theta_cmd"])

    state = PostprocessState()
    latencies = []
    frame_idx = 0

    while True:
        ok, frame = cap.read()
        if not ok or frame is None:
            break

        start = perf_counter()
        processed, _ = preprocess_frame(frame, model)
        inp = np.expand_dims(processed, axis=0)
        pred = float(model_tf.predict(inp, verbose=0).reshape(-1)[0])
        dt = 1.0 / fps
        theta_cmd = postprocess(pred, state, replay_cfg["postprocess"], dt)
        latency_ms = (perf_counter() - start) * 1000.0
        latencies.append(latency_ms)

        if out_writer is None and replay_cfg["outputs"]["write_overlay_video"]:
            height, width = frame.shape[:2]
            out_writer = cv2.VideoWriter(
                str(overlay_path),
                cv2.VideoWriter_fourcc(*"mp4v"),
                fps,
                (width, height),
            )

        if out_writer:
            overlay = frame.copy()
            cv2.putText(
                overlay,
                f"pred: {pred:.2f} cmd: {theta_cmd:.2f}",
                (20, 40),
                cv2.FONT_HERSHEY_SIMPLEX,
                1.0,
                (0, 255, 0),
                2,
            )
            out_writer.write(overlay)

        command_writer.writerow([frame_idx, pred, theta_cmd])

        if replay_cfg["outputs"]["ui_preview"]:
            cv2.imshow("replay", frame)
            key = cv2.waitKey(frame_delay_ms) & 0xFF
            if key == ord("q"):
                break
        else:
            cv2.waitKey(frame_delay_ms)

        frame_idx += 1

    cap.release()
    if out_writer:
        out_writer.release()
    commands_handle.close()
    cv2.destroyAllWindows()

    if latencies:
        latencies.sort()
        p50 = latencies[int(0.5 * len(latencies))]
        p95 = latencies[int(0.95 * len(latencies))]
        p99 = latencies[int(0.99 * len(latencies))]
    else:
        p50 = p95 = p99 = 0.0

    latency_path = Path("artifacts/reports") / f"{run_id}_latency.json"
    with open(latency_path, "w", encoding="utf-8") as handle:
        json.dump({"p50_ms": p50, "p95_ms": p95, "p99_ms": p99}, handle, indent=2)

    log_event(logger, "replay", "complete", run_id=run_id, exp_id=exp_id)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--system", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--replay", required=True)
    parser.add_argument("--run_id", required=True)
    parser.add_argument("--exp_id", required=True)
    args = parser.parse_args()
    replay(args.system, args.model, args.replay, args.run_id, args.exp_id)


if __name__ == "__main__":
    main()
