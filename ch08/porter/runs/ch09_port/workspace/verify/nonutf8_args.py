"""비UTF-8 명령행 인자(Linux 바이트 인자)를 기준 구현 main 과 Rust 바이너리로 비교한다.

0x80~0xFF 의 모든 바이트 b 를 다음 위치에 넣는다(인자는 bytes 로 그대로 전달):
  존재하는 파일 이름 안(b'f' + b + b'.csv'), 없는 파일 이름, 확장자 자리(b'x.cs' + b), 옵션 이름(b'--' + b, b'-' + b),
  -h 뒤(b'-h' + b), --format 값, --top 값, 공백이 든 '-' 시작 인자(b'-' + b + b' x').
비교: 종료 코드와 stdout(바이트). 계약 4절에 따라 FILE 이 UTF-8 이 아니면 stderr 는 비교하지 않고, 오류면 비어 있지 않은지만 본다.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RUST = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "rust_app" / "target" / "release" / "logstat"
PY = [sys.executable.encode(), str(ROOT / "python_src" / "logstat.py").encode()]
TMP = Path(tempfile.mkdtemp())
CSV = b"ts,method,path,status,bytes,latency_ms\n2026-10-29T00:00:00Z,GET,/a,200,1,1\n"
good = str(TMP / "good.csv").encode()
(TMP / "good.csv").write_bytes(CSV)


def run(cmd: list[bytes]) -> tuple[int, bytes, bytes]:
    p = subprocess.run(cmd, capture_output=True, cwd=TMP)
    return p.returncode, p.stdout, p.stderr


cases: list[tuple[str, list[bytes]]] = []
for b in range(0x80, 0x100):
    by = bytes([b])
    name = b"f" + by + b".csv"
    (TMP / name.decode("utf-8", "surrogateescape")).write_bytes(CSV)
    cases += [
        (f"existing {by!r}", [name]),
        (f"existing {by!r} --json", [name, b"--json"]),
        (f"missing {by!r}", [b"m" + by + b".csv"]),
        (f"ext {by!r}", [b"x.cs" + by]),
        (f"ext-format {by!r}", [b"x.cs" + by, b"--format", b"csv"]),
        (f"--opt {by!r}", [good, b"--" + by]),
        (f"-opt {by!r}", [good, b"-" + by]),
        (f"-h {by!r}", [good, b"-h" + by]),
        (f"format value {by!r}", [good, b"--format", b"csv" + by]),
        (f"top value {by!r}", [good, b"--top", b"1" + by]),
        (f"top= {by!r}", [good, b"--top=" + by]),
        (f"dash-space positional {by!r}", [b"-" + by + b" x", b"--format", b"csv"]),
    ]

failures = 0
codes: dict[int, int] = {}
for name, args in cases:
    py, rs = run(PY + args), run([str(RUST).encode()] + args)
    ok = py[0] == rs[0] and py[1] == rs[1] and (py[0] == 0 or rs[2] != b"")
    failures += not ok
    codes[py[0]] = codes.get(py[0], 0) + 1
    if not ok:
        print(f"FAIL {name}: python={py!r}\n     rust  ={rs!r}")
print("python exit codes:", dict(sorted(codes.items())))
print(f"{len(cases) - failures}/{len(cases)} non-UTF-8 argument cases match")
sys.exit(1 if failures else 0)
