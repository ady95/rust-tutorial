"""11-1·11-2: 호출 비용, 자료 변환 비용, NumPy 비교, GIL 해제 효과를 잰다.

사용법 (hello_ext 에서, maturin develop --release 뒤): uv run python bench_overhead.py [--out results.json]
"""

from __future__ import annotations

import argparse
import json
import random
import statistics
import threading
import time
import timeit

import numpy as np

import hello_ext


def best(stmt, number: int, repeat: int = 5) -> float:
    """한 번 실행에 걸린 시간(초)의 최솟값."""
    return min(timeit.repeat(stmt, number=number, repeat=repeat)) / number


def py_add(a: int, b: int) -> int:
    return a + b


def py_percentile(values: list[float], p: int) -> float:
    ordered = sorted(values)
    k = max((p * len(ordered) + 99) // 100, 1)
    return ordered[k - 1]


def threads_wall(fn, text: str, threads: int = 4) -> float:
    def work() -> None:
        for _ in range(3):
            fn(text)

    started = time.perf_counter()
    pool = [threading.Thread(target=work) for _ in range(threads)]
    for t in pool:
        t.start()
    for t in pool:
        t.join()
    return time.perf_counter() - started


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out")
    args = parser.parse_args()
    rng = random.Random(2026)
    out: dict[str, object] = {}

    out["call_ns"] = {"python_add": best(lambda: py_add(1, 2), 1_000_000) * 1e9,
                      "rust_add": best(lambda: hello_ext.add(1, 2), 1_000_000) * 1e9}

    sums = {}
    for n in (10, 1_000, 1_000_000):
        values = [rng.random() for _ in range(n)]
        array = np.array(values)
        number = max(1, 1_000_000 // n)
        sums[n] = {"python_sum": best(lambda: sum(values), number) * 1e6,
                   "rust_sum_floats(list)": best(lambda: hello_ext.sum_floats(values), number) * 1e6,
                   "numpy_sum(array)": best(lambda: array.sum(), number) * 1e6,
                   "numpy_sum(list->array)": best(lambda: np.array(values).sum(), number) * 1e6}
    out["sum_us"] = sums

    values = [rng.lognormvariate(3, 1) for _ in range(1_000_000)]
    array = np.array(values)
    assert py_percentile(values, 95) == hello_ext.percentile(values, 95) == float(
        np.percentile(array, 95, method="inverted_cdf"))
    out["percentile_1m_ms"] = {
        "python_sorted": best(lambda: py_percentile(values, 95), 1, 3) * 1e3,
        "rust_percentile(list)": best(lambda: hello_ext.percentile(values, 95), 1, 3) * 1e3,
        "numpy_percentile(array)": best(lambda: np.percentile(array, 95, method="inverted_cdf"), 1, 3) * 1e3,
        "list->Vec conversion only": best(lambda: hello_ext.sum_floats(values), 1, 3) * 1e3,
    }

    text = " ".join(rng.choice(["alpha", "beta", "gamma", "delta"]) for _ in range(2_000_000))
    single = statistics.median(threads_wall(hello_ext.count_words, text, 1) for _ in range(3))
    out["gil_4threads_s"] = {
        "one_thread": single,
        "detach(4 threads)": statistics.median(threads_wall(hello_ext.count_words, text) for _ in range(3)),
        "holding_gil(4 threads)": statistics.median(threads_wall(hello_ext.count_words_holding_gil, text) for _ in range(3)),
    }
    print(json.dumps(out, indent=2))
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fp:
            json.dump(out, fp, indent=2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
