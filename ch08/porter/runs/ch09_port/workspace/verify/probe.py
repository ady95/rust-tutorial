"""계획서의 '실측 필요' 항목을 기준 구현으로 확인한다."""

import csv
import io
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "python_src"))

import logstat  # noqa: E402

print("== ts")
for ts in ["2026-01-01T00:00:00+00:60", "2026-01-01T00:00:00+23:60", "2026-01-01T00:00:00+23:59",
           "2026-01-01T00:00:00-23:59", "2026-01-01T00:00:00+24:00", "2026-01-01T00:00:00+00:99",
           "2026-01-01T24:00:00Z", "2026-01-01T23:59:60Z", "0000-01-01T00:00:00Z", "2024-02-29T00:00:00Z",
           "2100-02-29T00:00:00Z", "9999-12-31T23:59:59-00:01", "0001-01-01T00:00:00+00:01",
           "0001-01-01T00:00:00-00:01", "2026-01-01T00:00:00.1234Z", "2026-01-01T00:00:00-00:00"]:
    try:
        print(ts, logstat.parse_ts(ts).isoformat())
    except logstat.BadRecord as e:
        print(ts, "BAD", e)

print("== csv NUL / quoting")
for text in ["a\0b,c\n", '"ab"cd,x\n', 'a"b,x\n', ' "a" ,x\n', '"abc', 'a\rb\r\nc\n', '"a\rb"\n', '""\n', "\n\n",
             '"a""b",c', 'x,"', "a,\n", ",\n"]:
    try:
        print(repr(text), list(csv.reader(io.StringIO(text, newline=""))))
    except csv.Error as e:
        print(repr(text), "ERR", e)

print("== json depth in run()")
for depth in (9996, 9997, 9998):
    line = '{"a":' * depth + "1" + "}" * depth
    print(depth, logstat.run(line + "\n", "jsonl", 10, False, True))
    line = "[" * depth + "]" * depth
    print("arr", depth, logstat.run(line + "\n", "jsonl", 10, False, True))

print("== json misc")
for s in ['"\\ud800"', '"\\ud800\\udc00"', "1e400", "-1e400", "-0", "-0.0", "1" * 4300, "1" * 4301, "-" + "1" * 4300,
          "1.5e99999999999999999999", "0.0e-99999999999999999999"]:
    try:
        print(s[:30], repr(json.loads(s)) if len(s) < 100 else "ok")
    except ValueError as e:
        print(s[:30], "ERR", type(e).__name__)

print("== lower() mapping to suffix letters")
hits = []
for cp in range(0x80, 0x110000):
    if 0xD800 <= cp <= 0xDFFF:
        continue
    low = chr(cp).lower()
    if any(ch in "csvjonld." for ch in low):
        hits.append((hex(cp), low))
print(hits)

print("== .1f")
print(f"{0.125:.1f}", f"{0.25:.1f}", f"{12.25:.1f}", f"{0.05:.1f}")
_ = datetime, timezone
