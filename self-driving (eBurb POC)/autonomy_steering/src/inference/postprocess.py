from dataclasses import dataclass
from typing import Optional


@dataclass
class PostprocessState:
    last_cmd: Optional[float] = None


def postprocess(theta_raw: float, state: PostprocessState, cfg: dict, dt: float) -> float:
    value = float(theta_raw)
    deadband = cfg.get("deadband", 0.0)
    if abs(value) < deadband:
        value = 0.0

    value = max(cfg.get("saturation_min", value), min(cfg.get("saturation_max", value), value))

    if state.last_cmd is None:
        state.last_cmd = value

    rate = cfg.get("rate_limit_deg_per_s", 0.0)
    if rate > 0 and dt > 0:
        max_delta = rate * dt
        delta = value - state.last_cmd
        if abs(delta) > max_delta:
            value = state.last_cmd + max_delta * (1 if delta > 0 else -1)

    alpha = cfg.get("smooth_alpha", 0.0)
    if alpha > 0:
        value = alpha * value + (1 - alpha) * state.last_cmd

    state.last_cmd = value
    return value
