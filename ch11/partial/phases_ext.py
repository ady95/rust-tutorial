"""11-3: 같은 프로세스 안에서 단계별 시간을 잰다. 기준 구현과 부분 이식(logstat_core)의 경계별 비용을 나눠 본다.

사용법 (부분 이식 작업 폴더에서): .venv/bin/python <이 파일> <데이터 파일> [--repeat 3]
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path.cwd() / "python_src"))

import logstat as ref  # noqa: E402
import logstat_core  # noqa: E402


def timed(fn, repeat: int):
    best, value = float("inf"), None
    for _ in range(repeat):
        start = time.perf_counter()
        value = fn()
        best = min(best, time.perf_counter() - start)
    return best, value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("data", type=Path)
    parser.add_argument("--repeat", type=int, default=3)
    args = parser.parse_args()
    csv = args.data.suffix == ".csv"
    text = args.data.read_bytes().decode("utf-8")
    if csv:
        t_py_parse, (rows, _) = timed(lambda: ref.read_csv(text), args.repeat)
        t_rs_parse, (rs_rows, _) = timed(lambda: logstat_core.read_csv(text, ref.Record, ref.BadRecord), args.repeat)
    else:
        t_py_parse, rows = timed(lambda: ref.read_jsonl(text), args.repeat)
        t_rs_parse, rs_rows = timed(lambda: logstat_core.read_jsonl(text, ref.Record, ref.BadRecord), args.repeat)
    records = [r for _, r in rows if not isinstance(r, ref.BadRecord)]
    t_py_sum, summary = timed(lambda: ref.summarize(records, len(rows) - len(records), 10), args.repeat)
    t_rs_all, (_, rs_summary) = timed(lambda: logstat_core.summarize(text, csv, 10, False), args.repeat)
    t_fmt, _ = timed(lambda: ref.format_text(rs_summary), args.repeat)
    assert ref.format_text(summary) == ref.format_text(rs_summary)
    result = {
        "rows": len(rows),
        "python: parse+validate": t_py_parse,
        "python: summarize": t_py_sum,
        "v1 rust: parse+validate -> Python objects": t_rs_parse,
        "v2 rust: parse+validate+summarize -> dict": t_rs_all,
        "python: format_text": t_fmt,
    }
    for key, value in result.items():
        print(f"{key:<46}{value if key == 'rows' else f'{value:8.3f}s'}")
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
