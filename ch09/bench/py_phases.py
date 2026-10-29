"""Python 기준 구현이 단계별로 시간을 어디에 쓰는지 잰다 (09-4).

단계: 파일 읽기와 UTF-8 해석 → 줄·필드 나누기만(csv.reader 또는 json.loads) → 검증과 Record 생성까지 → 집계 → 출력 문자열
"나누기만"은 검증 없이 같은 파서를 돌린 시간이고, "검증과 Record 생성"은 기준 구현의 read_csv/read_jsonl 전체 시간이다.

사용법: python3 py_phases.py ../logstat/python_src/logstat.py ~/work/ch09_data/logs_1000000.csv [--repeat 3]
"""

from __future__ import annotations

import argparse
import csv
import importlib.util
import io
import json
import sys
import time
from pathlib import Path


def load(path: Path):
    spec = importlib.util.spec_from_file_location("logstat_ref", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["logstat_ref"] = module
    spec.loader.exec_module(module)
    return module


def timed(fn, repeat: int):
    best, value = float("inf"), None
    for _ in range(repeat):
        start = time.perf_counter()
        value = fn()
        best = min(best, time.perf_counter() - start)
    return best, value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("reference", type=Path)
    parser.add_argument("data", type=Path)
    parser.add_argument("--repeat", type=int, default=3)
    args = parser.parse_args()
    ref = load(args.reference)
    fmt = "csv" if args.data.suffix == ".csv" else "jsonl"

    t_read, text = timed(lambda: args.data.read_bytes().decode("utf-8"), args.repeat)
    if fmt == "csv":
        t_split, _ = timed(lambda: sum(1 for _ in csv.reader(io.StringIO(text, newline=""))), args.repeat)
        t_parse, (rows, _) = timed(lambda: ref.read_csv(text), args.repeat)
    else:
        t_split, _ = timed(lambda: sum(1 for line in text.split("\n") if line and json.loads(line) is not None),
                           args.repeat)
        t_parse, rows = timed(lambda: ref.read_jsonl(text), args.repeat)
    records = [r for _, r in rows if not isinstance(r, ref.BadRecord)]
    skipped = len(rows) - len(records)
    t_sum, summary = timed(lambda: ref.summarize(records, skipped, 10), args.repeat)
    t_fmt, _ = timed(lambda: ref.format_text(summary), args.repeat)
    phases = [("read+decode", t_read), ("split only", t_split), ("parse+validate (incl. split)", t_parse),
              ("summarize", t_sum), ("format", t_fmt)]
    total = t_read + t_parse + t_sum + t_fmt
    print(f"{args.data.name}: {len(rows):,} rows, best of {args.repeat}")
    for name, t in phases:
        share = "" if name == "split only" else f"{t / total * 100:5.1f}%"
        print(f"  {name:<30}{t:8.3f}s {share}")
    print(f"  {'total (without split only)':<30}{total:8.3f}s")
    out = {name: t for name, t in phases} | {"total": total, "rows": len(rows)}
    print(json.dumps(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
