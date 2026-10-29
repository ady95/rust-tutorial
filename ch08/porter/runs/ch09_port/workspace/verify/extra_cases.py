"""compare/fuzz 가 덮지 않는 경우를 기준 구현(main, 하위 프로세스)과 Rust 실행 파일로 비교한다.

사용법: python3 verify/extra_cases.py [RUST_BIN]
비교: 종료 코드, stdout, stderr(바이트). usage=True 인 경우는 종료 코드와 stderr 가 비어 있지 않은지만.
"""

from __future__ import annotations

import json
import random
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RUST = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "rust_app" / "target" / "release" / "logstat"
PY = [sys.executable, str(ROOT / "python_src" / "logstat.py")]
TMP = Path(tempfile.mkdtemp())
HEADER = "ts,method,path,status,bytes,latency_ms\n"
GOOD = "2026-10-29T00:00:00Z,GET,/a,200,1,1\n"


def jl(**kw: object) -> str:
    base = {"ts": "2026-10-29T00:00:00Z", "method": "GET", "path": "/a", "status": 200, "bytes": 1, "latency_ms": 1}
    base.update(kw)
    return json.dumps(base, ensure_ascii=False)


def raw_jl(field: str, raw: str) -> str:
    """field 값을 JSON 텍스트 raw 그대로 넣은 한 줄."""
    return jl(**{field: "@@"}).replace('"@@"', raw)


cases: list[tuple[str, bytes | None, str, list[str], bool]] = []


def add(name: str, content: str | bytes | None, suffix: str = ".csv", args: list[str] | None = None,
        usage: bool = False) -> None:
    data = content.encode("utf-8") if isinstance(content, str) else content
    cases.append((name, data, suffix, args or [], usage))


# R1 첫 줄이 빈 줄
add("blank-first", "\n" + HEADER + GOOD)
add("crlf-first", "\r\n" + HEADER + GOOD)
add("space-first", " \n" + HEADER + GOOD)
add("quote-first", '""\n' + HEADER + GOOD)
# R2 필드 길이 경계와 순서
add("field-131072", HEADER + "2026-10-29T00:00:00Z,GET,/" + "x" * 131071 + ",200,1,1\n")
add("field-131073-multibyte", HEADER + "2026-10-29T00:00:00Z,GET,/" + "가" * 131072 + ",200,1,1\n")
add("field-header", "ts" + "x" * 131072 + ",method\n")
add("field-after-bad-strict", HEADER + "x\n" + GOOD + "a,b,/" + "x" * 131072 + ",c,d,e\n", args=["--strict"])
add("field-quoted-newlines", HEADER + '"' + "a\n" * 70000 + '"\n')
add("field-escaped-quotes", HEADER + GOOD + '2026-10-29T00:00:00Z,GET,"/' + '""' * 131071 + '",200,1,1\n')
# R3 비표준 인용
add("quoting-odd", HEADER + '2026-10-29T00:00:00Z,GET,"/ab"cd,200,1,1\n2026-10-29T00:00:00Z,GET,/a"b,200,1,1\n'
    '2026-10-29T00:00:00Z,GET, "/a",200,1,1\n2026-10-29T00:00:00Z,GET,"/a" ,200,1,1\r'
    '2026-10-29T00:00:00Z,GET,"/x\r\ny",200,1,1\r\n2026-10-29T00:00:00Z,GET,/n\0ul,200,1,1\n'
    '2026-10-29T00:00:00Z,GET,"/open,200,1,1\n')
add("dup-columns", "ts,method,path,status,bytes,latency_ms,path\n2026-10-29T00:00:00Z,GET,/first,200,1,1,/second\n")
add("csv-numbers", HEADER + "".join(f"2026-10-29T00:00:00Z,GET,/{i},200,{b},{lat}\n" for i, (b, lat) in enumerate([
    ("0" * 200 + "5", "1"), ("1000000000000", "1000000000.0000000000000001"), ("1000000000001", "1"),
    ("1", "1000000000.000001"), ("1", "0" * 50 + ".5"), ("1", "1." + "0" * 3000 + "1"), ("١", "1"), ("1", "١"),
    ("1", "1e3"), ("1", ".5"), ("1", "5."), ("", "1"), ("1", ""), ("01", "00.000"),
])), args=["--top", "100"])
add("csv-status", HEADER + "".join(f"2026-10-29T00:00:00Z,GET,/a,{s},1,1\n" for s in
                                     ["100", "199", "600", "099", "20", "2000", " 200", "٢00", "550"]))
add("csv-ws-lines", HEADER + GOOD + "   \n\t\n" + GOOD, args=["--strict"])
# R4 JSON
add("json-depth", "\n".join([
    jl()[:-1] + ',"deep":' + "[" * 9996 + "]" * 9996 + "}",
    jl()[:-1] + ',"deep":' + "[" * 9997 + "]" * 9997 + "}",
    "[" * 9997 + "]" * 9997, "[" * 9998 + "]" * 9998,
    '{"a":' * 9997 + "1" + "}" * 9997, '{"a":' * 9998 + "1" + "}" * 9998,
]) + "\n", ".jsonl")
add("json-digits", "\n".join([
    jl()[:-1] + ',"big":' + "1" * 4300 + "}", jl()[:-1] + ',"big":' + "1" * 4301 + "}",
    jl()[:-1] + ',"big":-' + "1" * 4300 + "}", jl()[:-1] + ',"big":-' + "1" * 4301 + "}",
    raw_jl("status", "1" * 4300), raw_jl("status", "1" * 4301), raw_jl("bytes", "-0"), raw_jl("bytes", "-1"),
    raw_jl("latency_ms", "1e400"), raw_jl("latency_ms", "-1e400"), raw_jl("latency_ms", "-0.0"),
    raw_jl("latency_ms", "Infinity"), raw_jl("latency_ms", "-Infinity"), raw_jl("latency_ms", "1000000000"),
    raw_jl("latency_ms", "1000000001"), raw_jl("latency_ms", "1e9"), raw_jl("latency_ms", "true"),
    raw_jl("latency_ms", "1000000000.0000001"), raw_jl("status", "2e2"), raw_jl("status", "false"),
]) + "\n", ".jsonl", ["--top", "50"])
add("json-syntax", "\n".join([
    jl()[:-1] + ',"x":"\\ud800"}', jl()[:-1] + ',"status":200}', '﻿' + jl(),
    raw_jl("bytes", "01"), raw_jl("bytes", "1."), raw_jl("bytes", ".5"), raw_jl("bytes", "-"), raw_jl("bytes", "+1"),
    raw_jl("latency_ms", "-NaN"), raw_jl("path", '"/a\x01"'), raw_jl("path", '"/a\x7f"'), jl()[:-1] + ",}",
    jl() + " x", "  " + jl() + "\t\r", '{"ts":"2026-10-29T00:00:00Z" , "method" : "GET","path":"/s","status":200,'
    '"bytes":1,"latency_ms":1 }', jl().replace('"method"', '"\\u006dethod"'), "null", '"s"', "1", "[]",
    raw_jl("path", '"/\\ud83d\\ude00"'), raw_jl("path", '"/\\u0000"'),
]) + "\n", ".jsonl", ["--top", "50"])
add("json-surrogate-outside-top", "\n".join([jl(path="/a"), jl(path="/a"), raw_jl("path", '"/\\ud800"')]) + "\n",
    ".jsonl", ["--top", "1"])
add("json-surrogate-in-top", "\n".join([jl(path="/a"), raw_jl("path", '"/\\ud800"')]) + "\n", ".jsonl")
add("json-surrogate-in-top-json", "\n".join([jl(path="/a"), raw_jl("path", '"/\\ud800"')]) + "\n", ".jsonl",
    ["--json"])
# 서로게이트 경로는 U+D7FF 보다 뒤(출력되지 않음), U+E000 보다 앞(출력되어 종료 1)이어야 한다
add("json-surrogate-order", "\n".join([raw_jl("path", '"/\\ud800"'), jl(path="/"), jl(path="/퟿"),
                                       jl(path="/\U00010000")]) + "\n", ".jsonl", ["--top", "1"])
add("json-surrogate-in-top-order", "\n".join([jl(path="/"), raw_jl("path", '"/\\ud800"')]) + "\n", ".jsonl",
    ["--top", "1"])
# R5 -0.0
add("neg-zero-a", "\n".join([raw_jl("latency_ms", "-0.0"), raw_jl("latency_ms", "0.0")]) + "\n", ".jsonl")
add("neg-zero-b", "\n".join([raw_jl("latency_ms", "0.0"), raw_jl("latency_ms", "-0.0")]) + "\n", ".jsonl", ["--json"])
# R6 ts
add("ts-edges", "\n".join(jl(ts=t, path="/" + t) for t in [
    "9999-12-31T23:59:59-00:01", "9999-12-31T23:59:59+00:01", "2026-01-01T00:00:00+23:59",
    "2026-01-01T00:00:00+24:00", "2024-02-29T00:00:00Z", "2100-02-29T00:00:00Z", "2000-02-29T12:00:00Z",
    "2026-01-01T00:00:00.5Z", "2026-01-01T00:00:00.123456+05:30", "2026-01-01T00:00:00.1234567Z",
    "2026-01-01T00:00:00+00:60", "2026-01-01T00:00:00+23:60", "2026-01-01T00:00:00-99:00",
    "0001-01-01T00:00:00-23:59", "0999-06-15T10:20:30Z", "2026-13-01T00:00:00Z", "2026-00-10T00:00:00Z",
    "2026-01-00T00:00:00Z", "2026-01-01T00:60:00Z", "2026-01-01t00:00:00Z", "2026-01-01T00:00:00z",
]) + "\n", ".jsonl", ["--top", "50"])
# R7 repr: 경로마다 지연값 하나 -> p50 이 그 값의 repr
rng = random.Random(7)
floats = [0.0001, 0.00012, 1e-05, 1.5e-07, 5e-324, 1e9, 123456789.125, 0.1 + 0.2, 1234567890123456.7 / 1e7,
          2.5e-05, 9.999999999999999e-05, 0.001, 1e-4 * 0.9999999]
floats += [rng.uniform(0, 1e9) for _ in range(300)] + [rng.uniform(0, 1e-3) for _ in range(300)]
floats += [10 ** rng.uniform(-320, 9) for _ in range(300)] + [round(rng.uniform(0, 5000), 3) for _ in range(300)]
add("repr", "".join(jl(path=f"/{i:04d}", latency_ms=x) + "\n" for i, x in enumerate(floats)), ".jsonl",
    ["--top", "100000"])
add("repr-json", "".join(jl(path=f"/{i:04d}", latency_ms=x) + "\n" for i, x in enumerate(floats)), ".jsonl",
    ["--top", "100000", "--json"])
# repr 최단 자릿수 동률(2^-25 = 2.9802322387695312e-08 등): 지연값 범위 안의 2의 거듭제곱과 짧은 이진 소수
ties = [2.0 ** -k for k in range(1, 1075)] + [i / 2 ** j for i in range(1, 200, 7) for j in range(20, 60)]
add("repr-ties", "".join(jl(path=f"/{i:05d}", latency_ms=x) + "\n" for i, x in enumerate(ties)), ".jsonl",
    ["--top", "100000"])
# R8 .1f: (n, e) 조합마다 경로 하나
lines = []
for n in range(1, 61):
    for e in range(n + 1):
        lines += [jl(path=f"/r{n}-{e}", status=500 if k < e else 200) for k in range(n)]
add("rate-table", "\n".join(lines) + "\n", ".jsonl", ["--top", "100000"])
# R10 공백 줄
add("jsonl-ws", "\n".join([jl(), "\f", "　", "\v", jl(path="/a b"), jl() + "\r", " "]) + "\n", ".jsonl",
    ["--json"])
add("jsonl-ws-strict", "\n".join([jl(), "  \r", "\f", jl()]) + "\n", ".jsonl", ["--strict"])
# R12 인자
add("args-repeat-json", HEADER + GOOD, args=["--json", "--json"])
add("args-repeat-format", HEADER + GOOD, args=["--format", "jsonl", "--format", "csv"])
add("args-top-eq", HEADER + GOOD, args=["--top=1"])
add("args-top-huge", HEADER + GOOD, args=["--top", "99999999999999999999999"])
add("args-top-4300", HEADER + GOOD, args=["--top", "0" * 4299 + "1"])
add("args-top-4301", HEADER + GOOD, args=["--top", "0" * 4300 + "1"], usage=True)
add("args-top-unicode", HEADER + GOOD, args=["--top", "٣"], usage=True)
add("args-json-eq", HEADER + GOOD, args=["--json=1"], usage=True)
add("args-two-files", HEADER + GOOD, args=["x.csv"], usage=True)
add("args-format-missing", HEADER + GOOD, args=["--format"], usage=True)
add("args-help", None, args=["--help"])
add("args-help-after-unknown", None, args=["--nope", "-h"])
add("args-hx", None, args=["-hx"])
add("args-top-zero-then-help", HEADER + GOOD, args=["--top", "0", "--help"], usage=True)
add("args-uppercase-ext", HEADER + GOOD, ".CSV")
add("args-ndjson", jl() + "\n", ".NDJson")
add("args-no-file", None, args=[], usage=True)
# R15 JSON 이스케이프
add("json-escapes", "\n".join([jl(path="/\x01\x7f \"\\\b\f\n\r\t/é"), jl(path="/\x1f")]) + "\n", ".jsonl",
    ["--json"])
add("text-raw-path", "\n".join([jl(path="/a\tb\nc")]) + "\n", ".jsonl")


def run(cmd: list[str]) -> tuple[int, bytes, bytes]:
    p = subprocess.run(cmd, capture_output=True, timeout=120, cwd=TMP)
    return p.returncode, p.stdout, p.stderr


special_args = {
    "args-two-files": lambda f: [f, "x.csv"],
    "args-no-file": lambda f: [],
    "args-help": lambda f: ["--help"],
    "args-help-after-unknown": lambda f: ["--nope", "-h"],
    "args-hx": lambda f: ["-hx"],
    "read-directory": lambda f: [str(TMP), "--format", "csv"],
    "read-notdir": lambda f: [f + "/x.csv"],
    "args-negative-file": lambda f: ["-5", "--format", "jsonl"],
}
add("read-directory", None)
add("read-notdir", HEADER)
add("args-negative-file", None)

failures = 0
for i, (name, data, suffix, args, usage) in enumerate(cases):
    path = TMP / f"case{i}{suffix}"
    if data is not None:
        path.write_bytes(data)
    argv = special_args[name](str(path)) if name in special_args else [str(path), *args]
    py, rs = run(PY + argv), run([str(RUST), *argv])
    if usage:
        ok = py[0] == rs[0] and rs[2] != b""
    elif name.startswith("json-surrogate-in-top"):
        ok = py[0] == rs[0] and py[1] == rs[1] == b"" and rs[2] != b""  # traceback 내용은 비교하지 않는다
    else:
        ok = py == rs
    failures += not ok
    print(f"{'OK  ' if ok else 'FAIL'} {name}  (exit {py[0]})")
    if not ok:
        print(f"     python={py[0]} {py[1][:300]!r} {py[2][-300:]!r}")
        print(f"     rust  ={rs[0]} {rs[1][:300]!r} {rs[2][-300:]!r}")
print(f"\n{len(cases) - failures}/{len(cases)} extra cases match")
sys.exit(1 if failures else 0)
