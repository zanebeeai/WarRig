# Autonomy Steering Pipeline

This repository contains a behavioral-cloning steering stack for a Windows 10/11 laptop with three front cameras and an Arduino-based steering encoder + DC motor controller. The pipeline records synchronized camera streams and steering labels, builds a dataset, trains a CNN regression model, runs replay inference, and optionally streams steering commands to the Arduino in bench mode.

## Setup

1. Create a virtual environment.
2. Install dependencies:

```
pip install -r requirements.txt
```

## Configuration

Update these files to match your hardware:

- `configs/system.yaml` (camera indices, resolution, serial COM port)
- `configs/model.yaml` (ROI, resize, preprocessing)
- `configs/train.yaml` (dataset id, training hyperparams)
- `configs/replay.yaml` (replay UI, postprocess)

## CLI Entry Points

All commands run through `src/app/main.py`.

Record a run (stop with Ctrl+C or use `--duration_s`):

```
python -m src.app.main record --config configs/system.yaml --duration_s 120
```

Build a dataset (uses all runs if none specified):

```
python -m src.app.main build_dataset --system configs/system.yaml --model configs/model.yaml --out_id runset_v1
```

Train a model:

```
python -m src.app.main train --model configs/model.yaml --train configs/train.yaml --exp_id exp_v1
```

Evaluate:

```
python -m src.app.main eval --exp_id exp_v1 --dataset_id runset_v1
```

Export SavedModel:

```
python -m src.app.main export --exp_id exp_v1 --model configs/model.yaml
```

Replay inference on a recorded run:

```
python -m src.app.main replay --system configs/system.yaml --model configs/model.yaml --replay configs/replay.yaml --run_id <run_id> --exp_id exp_v1
```

Bench stream steering commands (opt-in and gated):

```
python -m src.app.main bench_stream --system configs/system.yaml --commands_csv artifacts/reports/<run_id>_commands.csv --bench_mode --arm
```

## Notes

- Steering commands are only sent in bench mode and require explicit `--bench_mode` and `--arm` flags.
- No throttle commands exist in the protocol or code.
- Arduino must provide `LabelFrame` JSON lines with encoder-based steering and killswitch status.
