import argparse
import json
from pathlib import Path

import numpy as np
import tensorflow as tf

from src.train.train import _parse_example
from src.utils.config import load_yaml, save_json
from src.utils.logging import get_logger, log_event


def evaluate(exp_id: str, dataset_id: str) -> None:
    logger = get_logger("Eval")
    data_dir = Path("data/processed") / dataset_id
    tfrecord_path = data_dir / "test.tfrecord"

    ds = tf.data.TFRecordDataset(str(tfrecord_path))
    ds = ds.map(_parse_example).batch(64)

    model_path = Path("artifacts/checkpoints") / exp_id / "best.keras"
    model = tf.keras.models.load_model(str(model_path))

    y_true = []
    y_pred = []
    for batch_x, batch_y in ds:
        preds = model.predict(batch_x, verbose=0)
        y_true.append(batch_y.numpy().reshape(-1))
        y_pred.append(preds.reshape(-1))
    y_true = np.concatenate(y_true)
    y_pred = np.concatenate(y_pred)

    mae = float(np.mean(np.abs(y_pred - y_true)))
    rmse = float(np.sqrt(np.mean((y_pred - y_true) ** 2)))
    metrics = {"mae": mae, "rmse": rmse, "samples": int(len(y_true))}
    save_json(f"artifacts/reports/{exp_id}_test_metrics.json", metrics)
    log_event(logger, "eval", "complete", exp_id=exp_id, dataset_id=dataset_id)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--exp_id", required=True)
    parser.add_argument("--dataset_id", required=True)
    args = parser.parse_args()
    evaluate(args.exp_id, args.dataset_id)


if __name__ == "__main__":
    main()
