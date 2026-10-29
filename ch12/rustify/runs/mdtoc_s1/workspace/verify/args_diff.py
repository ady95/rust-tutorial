"""인자 조합을 Python 기준 구현과 Rust 바이너리로 돌려 비교한다(argparse 가장자리, int() 해석).

    python3 verify/args_diff.py [--depth N]

비교: 종료 코드, stdout(-h 가 아닐 때), stderr(사용법 오류는 비어 있지 않은지만, 도움말은 비어 있는지, 나머지는 바이트 단위).
표준 입력은 고정 문서다. 처음 한 줄은 -h 인 경우 stdout 내용을 비교하지 않는다는 뜻이다.
"""

from __future__ import annotations

import argparse
import itertools
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PY = [sys.executable, str(ROOT / "python_src" / "mdtoc.py")]
RS = [str(ROOT / "rust_app" / "target" / "release" / "mdtoc")]
STDIN = "# A\n## B\n### C\n".encode()

# 플랜 R11, R12 의 목록
LISTED = [
    ["--min=2"], ["--m", "2"], ["--json=1"], ["--help=x"], ["-h"], ["-hx"], ["-h", "--min-level", "9"],
    ["--min-level", "9", "-h"], ["--bogus", "-h"], ["a", "b"], ["a", "--json", "b"], ["--"], ["--", "--json"],
    ["-5"], ["-a b"], ["-a", "b"], ["--min-level"], ["--min-level", "--json"], ["--min-level", "-1"],
    ["--max-level="], [""], ["-"], ["-", "-"], ["-hh"], ["-hhx"], ["-h=x"], ["-h="], ["-hx", "-h"],
    ["--min-level", "--", "3"], ["--min-level", "3", "--"], ["--min-level=3", "--", "x"], ["--", "--"],
    ["--", "--", "--"], ["--json", "--", "tests/fixtures/basic.md"], ["tests/fixtures/basic.md", "--"],
    ["--max-level", "-- 3"], ["-.5"], ["-5.5"], ["-٣"], ["-5\n"], ["-5x"], ["--5"], ["-j"], ["-j", "-h"],
    ["--min-level", "3", "-j"], ["--JSON"], ["--json", "--json"], ["-H"], ["--min-level=٣"],
]
INT_VALUES = ["٣", " 3", "3 ", "+3", "03", "0_3", "3_", "_3", "3__0", "３", "-0", "3.0", "1e0", "٣٣", "\t3\n",
              "\x1c3", "\x1f3", " 3", "　3", "3 ", "\x0b3", "+ 3", "- 3", "++3", "0x3", "0b11",
              "1_0", "6", "7", "00000000000000000000006", "1" + "0" * 5000, "٣_٣", "²", "①", "٣a",
              "​3", "﻿3", "-3", "+0", "１", "𝟑", "6_", "٠٣"]
POOL = ["--json", "--min-level", "2", "--max-level=3", "-h", "--bogus", "a", "-", "--", "-5", "-hx", "--min-level=9",
        "x y", "tests/fixtures/basic.md", "-hh", "--help"]


def run(cmd: list[str], args: list[str]) -> tuple[int, bytes, bytes]:
    proc = subprocess.run(cmd + args, input=STDIN, capture_output=True, cwd=ROOT, timeout=60)
    return proc.returncode, proc.stdout, proc.stderr


def check(args: list[str]) -> str | None:
    py, rs = run(PY, args), run(RS, args)
    problems = []
    if py[0] != rs[0]:
        problems.append(f"exit python={py[0]} rust={rs[0]}")
    elif py[0] == 2:
        if py[1] or rs[1]:
            problems.append("stdout not empty on usage error")
        if not rs[2]:
            problems.append("rust stderr empty on usage error")
    elif py[0] == 0 and not py[1].startswith(b"usage:"):
        if py[1:] != rs[1:]:
            problems.append(f"output python={py[1:]!r} rust={rs[1:]!r}")
    elif py[0] == 0:  # help
        if not rs[1].startswith(b"usage:") or rs[2]:
            problems.append(f"help python={py[1:2]!r} rust={rs[1:]!r}")
    elif py[1:] != rs[1:]:
        problems.append(f"output python={py[1:]!r} rust={rs[1:]!r}")
    return f"{args!r}: " + "; ".join(problems) if problems else None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--depth", type=int, default=3)
    opts = parser.parse_args()
    cases = [list(a) for a in LISTED]
    for flag in ("--min-level", "--max-level"):
        for v in INT_VALUES:
            cases.append([flag, v])
            cases.append([f"{flag}={v}"])
    for n in range(1, opts.depth + 1):
        cases += [list(p) for p in itertools.product(POOL, repeat=n)]
    with ThreadPoolExecutor(8) as pool:
        results = list(pool.map(check, cases))
    bad = [r for r in results if r]
    for r in bad[:40]:
        print("MISMATCH", r)
    print(f"args_diff: {len(cases) - len(bad)}/{len(cases)} match")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
