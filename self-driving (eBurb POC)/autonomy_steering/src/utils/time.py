import time


def now_ns() -> int:
    return time.perf_counter_ns()


def now_ms() -> int:
    return int(time.time() * 1000)
