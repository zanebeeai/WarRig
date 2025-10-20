import argparse
import json
import random
from pathlib import Path

import numpy as np
import tensorflow as tf

from src.models.cnn_regression_v1 import build_model
from src.utils.config import ensure_dir, load_yaml, save_json
from src.utils.logging import get_logger, log_event


def _set_seeds(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    tf.random.set_seed(seed)


def _parse_example(example_proto: tf.Tensor) -> tuple:
    feature_desc = {
        "image": tf.io.FixedLenFeature([], tf.string),
        "label": tf.io.FixedLenFeature([1], tf.float32),
        "shape": tf.io.FixedLenFeature([3], tf.int64),
    }
    example = tf.io.parse_single_example(example_proto, feature_desc)
    shape = tf.cast(example["shape"], tf.int32)
    image = tf.io.decode_raw(example["image"], tf.float32)
    image = tf.reshape(image, shape)
    label = example["label"]
    return image, label


def _apply_augmentation(image: tf.Tensor, label: tf.Tensor, cfg: dict) -> tuple:
    aug = cfg.get("augmentation", {})
    if not aug.get("enabled", False):
        return image, label
    if aug.get("brightness_jitter", 0.0) > 0:
        image = tf.image.random_brightness(image, max_delta=aug["brightness_jitter"])
    if aug.get("gaussian_noise", 0.0) > 0:
        noise = tf.random.normal(tf.shape(image), stddev=aug["gaussian_noise"])
        image = image + noise
    return image, label


def train(model_cfg_path: str, train_cfg_path: str, exp_id: str) -> None:
    model_cfg = load_yaml(model_cfg_path)
    train_cfg = load_yaml(train_cfg_path)
    logger = get_logger("Train")

    _set_seeds(train_cfg["training"]["seed"])

    dataset_id = train_cfg["data"]["dataset_id"]
    data_dir = Path("data/processed") / dataset_id
    train_record = data_dir / "train.tfrecord"
    val_record = data_dir / "val.tfrecord"

    ds = tf.data.TFRecordDataset(str(train_record))
    ds = ds.map(_parse_example, num_parallel_calls=tf.data.AUTOTUNE)
    ds = ds.map(lambda x, y: _apply_augmentation(x, y, train_cfg), num_parallel_calls=tf.data.AUTOTUNE)

    batch_size = train_cfg["training"]["batch_size"]
    ds = ds.shuffle(1000).batch(batch_size).prefetch(tf.data.AUTOTUNE)

    model = build_model(model_cfg)
    optimizer_name = train_cfg["training"]["optimizer"]
    lr = train_cfg["training"]["lr"]
    optimizer = {
        "adam": tf.keras.optimizers.Adam(lr),
        "adamw": tf.keras.optimizers.AdamW(lr),
        "sgd": tf.keras.optimizers.SGD(lr),
    }[optimizer_name]
    loss_name = train_cfg["training"]["loss"]
    loss = {"mse": "mse", "mae": "mae", "huber": tf.keras.losses.Huber()}[loss_name]
    model.compile(optimizer=optimizer, loss=loss, metrics=train_cfg["training"]["metrics"])

    exp_dir = Path("artifacts/checkpoints") / exp_id
    ensure_dir(str(exp_dir))
    checkpoint_path = exp_dir / "best.keras"

    callbacks = []
    early = train_cfg["training"]["early_stopping"]
    if early.get("enabled", False):
        callbacks.append(
            tf.keras.callbacks.EarlyStopping(patience=early["patience"], restore_best_weights=True)
        )
    callbacks.append(
        tf.keras.callbacks.ModelCheckpoint(
            filepath=str(checkpoint_path),
            save_best_only=train_cfg["training"]["checkpointing"]["save_best_only"],
            monitor=train_cfg["training"]["checkpointing"]["monitor"],
        )
    )

    val_ds = None
    if val_record.exists() and val_record.stat().st_size > 0:
        val_ds = tf.data.TFRecordDataset(str(val_record))
        val_ds = val_ds.map(_parse_example, num_parallel_calls=tf.data.AUTOTUNE)
        val_ds = val_ds.batch(batch_size).prefetch(tf.data.AUTOTUNE)

    history = model.fit(
        ds,
        epochs=train_cfg["training"]["epochs"],
        callbacks=callbacks,
        validation_data=val_ds,
    )
    history_path = Path("artifacts/reports") / f"{exp_id}_history.json"
    save_json(str(history_path), history.history)

    manifest = {
        "exp_id": exp_id,
        "dataset_id": dataset_id,
        "model_config": model_cfg_path,
        "train_config": train_cfg_path,
        "checkpoint": str(checkpoint_path),
    }
    save_json(f"artifacts/reports/{exp_id}_manifest.json", manifest)
    log_event(logger, "train", "complete", exp_id=exp_id, dataset_id=dataset_id)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True)
    parser.add_argument("--train", required=True)
    parser.add_argument("--exp_id", required=True)
    args = parser.parse_args()
    train(args.model, args.train, args.exp_id)


if __name__ == "__main__":
    main()
