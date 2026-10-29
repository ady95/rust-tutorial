"""logstat 의 '한 번 읽으며 집계' 변형 (09-4). 출력은 기준 구현과 바이트 단위로 같다.

기준 구현은 모든 Record 를 리스트에 담은 뒤 summarize() 로 다시 훑는다. 이 변형은 같은 검증 함수를 쓰되
Record 를 보관하지 않고, 백분위수에 필요한 latency 값(전체, 경로별)과 개수만 모은다.
바꾼 것은 집계 방식(알고리즘·자료구조)뿐이고 언어와 검증 코드는 같다.

사용법: python3 logstat_stream.py FILE [기준 구현과 같은 인자]
"""

from __future__ import annotations

import csv
import importlib.util
import io
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

_ref_path = Path(__file__).resolve().parents[2] / "logstat" / "python_src" / "logstat.py"
_spec = importlib.util.spec_from_file_location("logstat_ref", _ref_path)
ref = importlib.util.module_from_spec(_spec)
sys.modules["logstat_ref"] = ref
_spec.loader.exec_module(ref)


class FileError(Exception):
    """파일 전체를 거부하는 오류(CSV 헤더 누락, 너무 긴 필드)."""


def iter_csv(text: str):
    """ref.read_csv 와 같은 규칙이지만 목록을 만들지 않고 (번호, Record 또는 오류)를 하나씩 내보낸다."""
    reader = csv.reader(io.StringIO(text, newline=""))
    try:
        header = next(reader, None)
    except csv.Error:
        raise FileError("header: csv field too large") from None
    if header is None:
        return
    for name in ref.FIELDS:
        if name not in header:
            raise FileError(f"missing column: {name}")
    number = 0
    while True:
        try:
            row = next(reader, None)
        except csv.Error:
            raise FileError(f"record {number + 1}: csv field too large") from None
        if row is None:
            return
        if not row:
            continue
        number += 1
        if len(row) != len(header):
            yield number, ref.BadRecord("bad field count")
            continue
        try:
            yield number, ref.record_from_strings(dict(zip(header, row)))
        except ref.BadRecord as err:
            yield number, err


def iter_jsonl(text: str):
    number = 0
    for line in text.split("\n"):
        if not line.strip(" \t\r"):
            continue
        number += 1
        try:
            obj = json.loads(line)
        except (ValueError, RecursionError):
            yield number, ref.BadRecord("invalid json")
            continue
        if not isinstance(obj, dict):
            yield number, ref.BadRecord("not an object")
            continue
        try:
            yield number, ref.record_from_json(obj)
        except ref.BadRecord as err:
            yield number, err


class Aggregate:
    def __init__(self) -> None:
        self.records = 0
        self.skipped = 0
        self.first = None
        self.last = None
        self.bytes = 0
        self.statuses: Counter[str] = Counter()
        self.methods: Counter[str] = Counter()
        self.minutes: Counter[str] = Counter()
        self.latencies: list[float] = []
        self.path_latency: dict[str, list[float]] = defaultdict(list)
        self.path_errors: Counter[str] = Counter()

    def add(self, r) -> None:
        self.records += 1
        ts = r.ts
        if self.first is None or ts < self.first:
            self.first = ts
        if self.last is None or ts > self.last:
            self.last = ts
        self.bytes += r.bytes
        self.statuses[f"{r.status // 100}xx"] += 1
        self.methods[r.method] += 1
        self.minutes[f"{ts.year:04d}-{ts.month:02d}-{ts.day:02d}T{ts.hour:02d}:{ts.minute:02d}Z"] += 1
        self.latencies.append(r.latency_ms)
        self.path_latency[r.path].append(r.latency_ms)
        if r.status >= 500:
            self.path_errors[r.path] += 1

    def summary(self, top_n: int) -> dict[str, object]:
        nr = ref.nearest_rank
        paths = sorted(self.path_latency.items(), key=lambda item: (-len(item[1]), item[0]))[:top_n]
        top = []
        for path, values in paths:
            values = sorted(values)
            top.append({"path": path, "count": len(values),
                        "error_rate": f"{self.path_errors[path] / len(values) * 100:.1f}%",
                        "p50": nr(values, 50), "p95": nr(values, 95)})
        lat = sorted(self.latencies)
        peak = min(self.minutes.items(), key=lambda item: (-item[1], item[0])) if self.minutes else None
        has = self.records > 0
        return {
            "records": self.records, "skipped": self.skipped,
            "first": ref.iso_utc(self.first) if has else None, "last": ref.iso_utc(self.last) if has else None,
            "bytes": self.bytes,
            "status": {k: self.statuses[k] for k in ("2xx", "3xx", "4xx", "5xx")},
            "methods": dict(sorted(self.methods.items(), key=lambda item: (-item[1], item[0]))),
            "latency_ms": {p: nr(lat, int(p[1:])) for p in ("p50", "p95", "p99")} if has else None,
            "peak_minute": {"minute": peak[0], "count": peak[1]} if peak else None,
            "top_paths": top,
        }


def run(text: str, fmt: str, top_n: int, as_json: bool, strict: bool) -> tuple[int, str, str]:
    agg = Aggregate()
    first_bad = None  # --strict 의 첫 오류. 파일 전체 오류(너무 긴 필드)가 뒤에 있으면 그쪽이 우선이라 끝까지 읽는다
    try:
        for number, item in iter_csv(text) if fmt == "csv" else iter_jsonl(text):
            if isinstance(item, ref.BadRecord):
                if strict and first_bad is None:
                    first_bad = (number, item)
                agg.skipped += 1
            elif first_bad is None:
                agg.add(item)
    except FileError as err:
        return ref.EXIT_INPUT_ERROR, "", f"logstat: error: {err}\n"
    if first_bad is not None:
        return ref.EXIT_INPUT_ERROR, "", f"logstat: error: record {first_bad[0]}: {first_bad[1]}\n"
    summary = agg.summary(top_n)
    out = json.dumps(summary, ensure_ascii=False, separators=(",", ":")) + "\n" if as_json else ref.format_text(summary)
    return ref.EXIT_OK, out, ""


if __name__ == "__main__":
    ref.run = run  # main() 의 파일 읽기·인자 처리는 그대로 쓰고 본체만 바꾼다
    sys.exit(ref.main())
