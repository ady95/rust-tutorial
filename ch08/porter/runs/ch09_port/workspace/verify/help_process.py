"""-h 출력을 실제 프로세스로 비교한다: COLUMNS/LINES 환경 변수 조합, 비UTF-8 값, pty 터미널 폭.

사용법: python3 verify/help_process.py [RUST_BIN]
"""

from __future__ import annotations

import fcntl
import os
import pty
import struct
import subprocess
import sys
import termios
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RUST = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "rust_app" / "target" / "release" / "logstat"
PY = [sys.executable, str(ROOT / "python_src" / "logstat.py")]


def base_env() -> dict[bytes, bytes]:
    return {k: v for k, v in os.environb.items() if k not in (b"COLUMNS", b"LINES")}


def run_pipe(cmd: list[str], env: dict[bytes, bytes]) -> tuple[int, bytes]:
    p = subprocess.run(cmd + ["-h"], capture_output=True, env=env)
    return p.returncode, p.stdout


def run_pty(cmd: list[str], env: dict[bytes, bytes], cols: int) -> tuple[int, bytes]:
    master, slave = pty.openpty()
    fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", 24, cols, 0, 0))
    attrs = termios.tcgetattr(slave)
    attrs[1] &= ~termios.OPOST  # 줄 끝 \n -> \r\n 변환을 끈다
    termios.tcsetattr(slave, termios.TCSANOW, attrs)
    p = subprocess.Popen(cmd + ["-h"], stdout=slave, stderr=subprocess.DEVNULL, env=env)
    os.close(slave)
    chunks = []
    while True:
        try:
            data = os.read(master, 65536)
        except OSError:
            break
        if not data:
            break
        chunks.append(data)
    os.close(master)
    return p.wait(), b"".join(chunks)


cases: list[tuple[str, dict[bytes, bytes], int | None]] = []
for value in [None, b"", b"0", b"-3", b"abc", b"1", b"30", b"50", b"79", b"81", b"120", b" 60 ", b"6_0",
              "٦٠".encode(), b"\xff60", b"60\xff", b"1" * 5000, b"99999999999999999999"]:
    for lines in [None, b"24", b"0"]:
        env = base_env()
        if value is not None:
            env[b"COLUMNS"] = value
        if lines is not None:
            env[b"LINES"] = lines
        cases.append((f"pipe COLUMNS={value!r} LINES={lines!r}", env, None))
for cols in [0, 1, 20, 40, 60, 79, 80, 81, 100, 200, 500]:
    for value in [None, b"0", b"45", b"x"]:
        env = base_env()
        if value is not None:
            env[b"COLUMNS"] = value
        cases.append((f"pty cols={cols} COLUMNS={value!r}", env, cols))

failures = 0
for name, env, cols in cases:
    if cols is None:
        py, rs = run_pipe(PY, env), run_pipe([str(RUST)], env)
    else:
        py, rs = run_pty(PY, env, cols), run_pty([str(RUST)], env, cols)
    ok = py == rs and py[0] == 0 and py[1] != b""
    failures += not ok
    print(f"{'OK  ' if ok else 'FAIL'} {name}")
    if not ok:
        print(f"     python={py!r}\n     rust  ={rs!r}")
print(f"\n{len(cases) - failures}/{len(cases)} help cases match")
sys.exit(1 if failures else 0)
