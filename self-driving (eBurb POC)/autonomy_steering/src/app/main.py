import argparse

from src.capture.record_run import record_run
from src.dataset.build_dataset import build_dataset
from src.eval.evaluate import evaluate
from src.inference.replay import replay
from src.interfaces.bench_stream import stream_from_csv
from src.train.export_model import export_model
from src.train.train import train


def main() -> None:
    parser = argparse.ArgumentParser(description="Autonomy steering pipeline")
    sub = parser.add_subparsers(dest="command", required=True)

    record = sub.add_parser("record")
    record.add_argument("--config", required=True)
    record.add_argument("--duration_s", type=float, default=0.0)

    build = sub.add_parser("build_dataset")
    build.add_argument("--system", required=True)
    build.add_argument("--model", required=True)
    build.add_argument("--out_id", required=True)
    build.add_argument("--runs", nargs="+", default=[])

    train_p = sub.add_parser("train")
    train_p.add_argument("--model", required=True)
    train_p.add_argument("--train", required=True)
    train_p.add_argument("--exp_id", required=True)

    eval_p = sub.add_parser("eval")
    eval_p.add_argument("--exp_id", required=True)
    eval_p.add_argument("--dataset_id", required=True)

    export_p = sub.add_parser("export")
    export_p.add_argument("--exp_id", required=True)
    export_p.add_argument("--model", required=True)

    replay_p = sub.add_parser("replay")
    replay_p.add_argument("--system", required=True)
    replay_p.add_argument("--model", required=True)
    replay_p.add_argument("--replay", required=True)
    replay_p.add_argument("--run_id", required=True)
    replay_p.add_argument("--exp_id", required=True)

    bench_p = sub.add_parser("bench_stream")
    bench_p.add_argument("--system", required=True)
    bench_p.add_argument("--commands_csv", required=True)
    bench_p.add_argument("--bench_mode", action="store_true")
    bench_p.add_argument("--arm", action="store_true")

    args = parser.parse_args()

    if args.command == "record":
        record_run(args.config, args.duration_s)
    elif args.command == "build_dataset":
        build_dataset(args.system, args.model, args.out_id, args.runs)
    elif args.command == "train":
        train(args.model, args.train, args.exp_id)
    elif args.command == "eval":
        evaluate(args.exp_id, args.dataset_id)
    elif args.command == "export":
        export_model(args.exp_id, args.model)
    elif args.command == "replay":
        replay(args.system, args.model, args.replay, args.run_id, args.exp_id)
    elif args.command == "bench_stream":
        stream_from_csv(args.system, args.commands_csv, args.bench_mode, args.arm)


if __name__ == "__main__":
    main()
