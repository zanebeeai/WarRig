import argparse
import json
from pathlib import Path

import tensorflow as tf

from src.utils.config import ensure_dir, load_yaml
from src.utils.logging import get_logger, log_event


def export_model(exp_id: str, model_cfg_path: str) -> None:
    logger = get_logger("Export")
    model_cfg = load_yaml(model_cfg_path)

    checkpoint = Path("artifacts/checkpoints") / exp_id / "best.keras"
    model = tf.keras.models.load_model(str(checkpoint))

    export_dir = Path("artifacts/exports") / exp_id / "saved_model"
    ensure_dir(str(export_dir))
    model.save(str(export_dir))

    preprocess_path = Path("artifacts/exports") / exp_id / "preprocess.json"
    with open(preprocess_path, "w", encoding="utf-8") as handle:
        json.dump(model_cfg, handle, indent=2)

    log_event(logger, "export", "complete", exp_id=exp_id, export_dir=str(export_dir))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--exp_id", required=True)
    parser.add_argument("--model", required=True)
    args = parser.parse_args()
    export_model(args.exp_id, args.model)


if __name__ == "__main__":
    main()
