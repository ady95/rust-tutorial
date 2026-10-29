"""logstat: CSV·JSON Lines 접근 로그를 요약하는 CLI (09장 기준 구현).

동작 계약은 contracts/behavior_spec.md 에 있다. 이 파일이 그 계약의 기준 구현이다.
run() 은 입출력 없이 (종료 코드, stdout, stderr) 를 돌려주는 순수 함수이고, main() 이 파일과 표준 출력을 다룬다.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone

EXIT_OK = 0
EXIT_INPUT_ERROR = 1
EXIT_USAGE_ERROR = 2

FIELDS = ("ts", "method", "path", "status", "bytes", "latency_ms")
MAX_BYTES = 10**12
MAX_LATENCY_MS = 1e9
METHODS = {"GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"}

# \d 는 Unicode 숫자도 받으므로 [0-9] 를 쓴다 (계약 3절)
TS_RE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(\.[0-9]{1,6})?(Z|[+-][0-9]{2}:[0-9]{2})")
STATUS_RE = re.compile(r"[1-5][0-9]{2}")
UINT_RE = re.compile(r"[0-9]+")
LATENCY_RE = re.compile(r"[0-9]+(\.[0-9]+)?")


class BadRecord(Exception):
    """계약 3절을 어긴 레코드. 메시지는 계약 4절의 이유 문자열."""


@dataclass(frozen=True)
class Record:
    ts: datetime  # UTC
    method: str
    path: str
    status: int
    bytes: int
    latency_ms: float


def parse_ts(value: object) -> datetime:
    if not isinstance(value, str) or not TS_RE.fullmatch(value):
        raise BadRecord("bad ts")
    try:
        return datetime.fromisoformat(value).astimezone(timezone.utc)
    except (ValueError, OverflowError):  # 2월 30일, 25시, UTC 로 바꾸면 1년보다 앞서는 시각 등
        raise BadRecord("bad ts") from None


def parse_path(value: object) -> str:
    if not isinstance(value, str) or not value.startswith("/"):
        raise BadRecord("bad path")
    return value.split("?", 1)[0]


def is_json_int(value: object) -> bool:
    return type(value) is int  # bool 은 int 의 하위 클래스라 isinstance 로는 걸러지지 않는다


def record_from_strings(row: dict[str, str]) -> Record:
    """CSV 한 행. 모든 필드가 문자열이다."""
    method = row["method"]
    if method not in METHODS:
        raise BadRecord("bad method")
    if not STATUS_RE.fullmatch(row["status"]):
        raise BadRecord("bad status")
    # int() 는 4300자리가 넘는 문자열(앞의 0 포함)을 거부(ValueError)하므로 0을 떼고 길이로 먼저 거른다
    digits = row["bytes"].lstrip("0") or "0"
    if not UINT_RE.fullmatch(row["bytes"]) or len(digits) > 13 or int(digits) > MAX_BYTES:
        raise BadRecord("bad bytes")
    if not LATENCY_RE.fullmatch(row["latency_ms"]) or float(row["latency_ms"]) > MAX_LATENCY_MS:
        raise BadRecord("bad latency_ms")
    return Record(parse_ts(row["ts"]), method, parse_path(row["path"]), int(row["status"]), int(digits),
                  float(row["latency_ms"]))


def record_from_json(obj: dict[str, object]) -> Record:
    """JSON Lines 한 줄. 숫자 필드는 JSON 숫자여야 한다."""
    for name in FIELDS:
        if name not in obj:
            raise BadRecord(f"missing field: {name}")
    method = obj["method"]
    if not isinstance(method, str) or method not in METHODS:
        raise BadRecord("bad method")
    status = obj["status"]
    if not is_json_int(status) or not 100 <= status <= 599:
        raise BadRecord("bad status")
    size = obj["bytes"]
    if not is_json_int(size) or not 0 <= size <= MAX_BYTES:
        raise BadRecord("bad bytes")
    latency = obj["latency_ms"]
    if not (is_json_int(latency) or type(latency) is float) or not 0 <= latency <= MAX_LATENCY_MS:
        raise BadRecord("bad latency_ms")  # NaN 은 비교가 모두 False 라 여기서 걸린다
    return Record(parse_ts(obj["ts"]), method, parse_path(obj["path"]), status, size, float(latency))


def read_csv(text: str) -> tuple[list[tuple[int, Record | BadRecord]], str | None]:
    """(레코드 번호, 레코드 또는 오류) 목록과, 파일 전체를 거부하는 오류 메시지(헤더 누락, 너무 긴 필드)."""
    reader = csv.reader(io.StringIO(text, newline=""))
    try:
        header = next(reader, None)
    except csv.Error:
        return [], "header: csv field too large"
    if header is None:
        return [], None
    for name in FIELDS:
        if name not in header:
            return [], f"missing column: {name}"
    out: list[tuple[int, Record | BadRecord]] = []
    number = 0
    while True:
        try:
            row = next(reader, None)
        except csv.Error:  # 필드가 csv.field_size_limit()(131072자)보다 길면
            return out, f"record {number + 1}: csv field too large"
        if row is None:
            break
        if not row:  # 빈 줄
            continue
        number += 1
        if len(row) != len(header):
            out.append((number, BadRecord("bad field count")))
            continue
        try:
            out.append((number, record_from_strings(dict(zip(header, row)))))
        except BadRecord as err:
            out.append((number, err))
    return out, None


def read_jsonl(text: str) -> list[tuple[int, Record | BadRecord]]:
    out: list[tuple[int, Record | BadRecord]] = []
    number = 0
    for line in text.split("\n"):  # splitlines() 는 U+2028 등에서도 나누므로 쓰지 않는다
        if not line.strip(" \t\r"):
            continue
        number += 1
        try:
            obj = json.loads(line)
        except (ValueError, RecursionError):  # 아주 깊게 중첩된 JSON 은 RecursionError
            out.append((number, BadRecord("invalid json")))
            continue
        if not isinstance(obj, dict):
            out.append((number, BadRecord("not an object")))
            continue
        try:
            out.append((number, record_from_json(obj)))
        except BadRecord as err:
            out.append((number, err))
    return out


def nearest_rank(sorted_values: list[float], p: int) -> float:
    k = (p * len(sorted_values) + 99) // 100  # ceil(p/100 * n), 정수로만 계산
    return sorted_values[max(k, 1) - 1]


def iso_utc(ts: datetime) -> str:
    return ts.isoformat()  # 2026-10-29T03:00:00+00:00, 마이크로초가 있으면 .ffffff


def summarize(records: list[Record], skipped: int, top_n: int) -> dict[str, object]:
    statuses = Counter(f"{r.status // 100}xx" for r in records)
    methods = Counter(r.method for r in records)
    # strftime("%Y") 는 Linux 에서 1000년 미만을 0으로 채우지 않으므로 직접 만든다
    minutes = Counter(f"{r.ts.year:04d}-{r.ts.month:02d}-{r.ts.day:02d}T{r.ts.hour:02d}:{r.ts.minute:02d}Z"
                      for r in records)
    by_path: dict[str, list[Record]] = defaultdict(list)
    for r in records:
        by_path[r.path].append(r)
    latencies = sorted(r.latency_ms for r in records)

    paths = sorted(by_path.items(), key=lambda item: (-len(item[1]), item[0]))[:top_n]
    top = []
    for path, rows in paths:
        values = sorted(r.latency_ms for r in rows)
        errors = sum(1 for r in rows if r.status >= 500)
        top.append({"path": path, "count": len(rows), "error_rate": f"{errors / len(rows) * 100:.1f}%",
                    "p50": nearest_rank(values, 50), "p95": nearest_rank(values, 95)})
    peak = min(minutes.items(), key=lambda item: (-item[1], item[0])) if minutes else None
    return {
        "records": len(records),
        "skipped": skipped,
        "first": iso_utc(min(r.ts for r in records)) if records else None,
        "last": iso_utc(max(r.ts for r in records)) if records else None,
        "bytes": sum(r.bytes for r in records),
        "status": {k: statuses[k] for k in ("2xx", "3xx", "4xx", "5xx")},
        "methods": dict(sorted(methods.items(), key=lambda item: (-item[1], item[0]))),
        "latency_ms": {p: nearest_rank(latencies, int(p[1:])) for p in ("p50", "p95", "p99")} if records else None,
        "peak_minute": {"minute": peak[0], "count": peak[1]} if peak else None,
        "top_paths": top,
    }


def format_text(s: dict[str, object]) -> str:
    lat = s["latency_ms"]
    peak = s["peak_minute"]
    lines = [
        f"records: {s['records']}",
        f"skipped: {s['skipped']}",
        f"range: {s['first']} .. {s['last']}" if s["first"] else "range: -",
        f"bytes: {s['bytes']}",
        "status: " + " ".join(f"{k}={v}" for k, v in s["status"].items()),
        "methods: " + (" ".join(f"{k}={v}" for k, v in s["methods"].items()) or "-"),
        f"latency_ms: p50={lat['p50']!r} p95={lat['p95']!r} p99={lat['p99']!r}" if lat else "latency_ms: -",
        f"peak_minute: {peak['minute']} {peak['count']}" if peak else "peak_minute: -",
        "top_paths:",
    ]
    lines += [f"{t['count']}\t{t['error_rate']}\t{t['p50']!r}\t{t['p95']!r}\t{t['path']}" for t in s["top_paths"]]
    return "\n".join(lines) + "\n"


def run(text: str, fmt: str, top_n: int, as_json: bool, strict: bool) -> tuple[int, str, str]:
    """입출력 없는 본체. (종료 코드, stdout, stderr)."""
    if fmt == "csv":
        rows, header_error = read_csv(text)
        if header_error:
            return EXIT_INPUT_ERROR, "", f"logstat: error: {header_error}\n"
    else:
        rows = read_jsonl(text)
    records: list[Record] = []
    skipped = 0
    for number, item in rows:
        if isinstance(item, BadRecord):
            if strict:
                return EXIT_INPUT_ERROR, "", f"logstat: error: record {number}: {item}\n"
            skipped += 1
        else:
            records.append(item)
    summary = summarize(records, skipped, top_n)
    out = json.dumps(summary, ensure_ascii=False, separators=(",", ":")) + "\n" if as_json else format_text(summary)
    return EXIT_OK, out, ""


def positive_int(value: str) -> int:
    if not UINT_RE.fullmatch(value) or int(value) < 1:
        raise argparse.ArgumentTypeError(f"not a positive integer: {value}")
    return int(value)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="logstat", description="Summarize CSV or JSON Lines access logs.",
                                     allow_abbrev=False)
    parser.add_argument("file")
    parser.add_argument("--format", choices=["csv", "jsonl"], help="default: from the file extension")
    parser.add_argument("--top", type=positive_int, default=10)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--strict", action="store_true", help="stop at the first bad record")
    return parser


def main(argv: list[str] | None = None) -> int:
    sys.stdout.reconfigure(encoding="utf-8", newline="\n")
    sys.stderr.reconfigure(encoding="utf-8", errors="backslashreplace", newline="\n")
    parser = build_parser()
    args = parser.parse_args(argv)
    fmt = args.format
    if fmt is None:
        lower = args.file.lower()
        fmt = "csv" if lower.endswith(".csv") else "jsonl" if lower.endswith((".jsonl", ".ndjson")) else None
        if fmt is None:
            parser.error("cannot infer --format from the file name")
    try:
        with open(args.file, "rb") as fp:
            data = fp.read()
    except FileNotFoundError:
        print(f"logstat: error: file not found: {args.file}", file=sys.stderr)
        return EXIT_INPUT_ERROR
    except OSError:
        print(f"logstat: error: cannot read file: {args.file}", file=sys.stderr)
        return EXIT_INPUT_ERROR
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        print(f"logstat: error: not valid UTF-8: {args.file}", file=sys.stderr)
        return EXIT_INPUT_ERROR
    code, out, err = run(text, fmt, args.top, args.json, args.strict)
    sys.stdout.write(out)
    sys.stderr.write(err)
    return code


if __name__ == "__main__":
    sys.exit(main())
