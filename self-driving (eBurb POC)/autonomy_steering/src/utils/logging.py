import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any, Dict


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    return logger


def log_event(logger: logging.Logger, module: str, event: str, **fields: Any) -> None:
    payload: Dict[str, Any] = {
        "ts": _utc_now(),
        "module": module,
        "event": event,
    }
    payload.update(fields)
    logger.info(json.dumps(payload, sort_keys=True))
