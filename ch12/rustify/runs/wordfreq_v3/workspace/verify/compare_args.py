"""명령행·경로 처리의 가장자리 경우를 기준 구현과 Rust 구현에 똑같이 실행해 비교한다.

비교 규칙은 automation/ 과 같다. 기준 구현이 2로 끝나면(인자 오류) 종료 코드와 "Rust stderr 가 비어 있지 않음"만,
그 밖에는 종료 코드·stdout·stderr 를 바이트 단위로 비교한다. -h/--help 의 stdout 도 바이트 단위로 비교한다.

사용법: python3 verify/compare_args.py [--rust rust_app/target/release/wordfreq] [--show]
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REFERENCE = ROOT / "python_src" / "wordfreq.py"

B = b"basic.txt"
CASES: list[list[bytes]] = [
    [b"-h"], [b"--help"], [b"--h"], [b"--he"], [b"-hh"], [b"-hhh"], [b"-hx"], [b"-h="], [b"--help=x"],
    [B, b"-h"], [b"-h", B], [b"--bogus", b"-h"], [b"a", b"b", b"-h"], [b"-h", b"--top", b"0"],
    [b"--top", b"0", b"-h"], [b"--top", b"-h"], [b"--", b"-h"],
    [B, b"--to", b"2"], [B, b"--t=2"], [B, b"--to=2"], [B, b"--js"], [B, b"--j"], [B, b"--json=1"],
    [B, b"--json="], [B, b"--top="], [B, b"--top"], [B, b"--top", b"--json"], [B, b"--top", b"-5"],
    [B, b"--top", b"-1"], [B, b"--top", b"0", b"--top", b"2"], [B, b"--top", b"2", b"--top", b"0"],
    [B, b"extra.txt"], [b"--", b"-x"], [b"-5"], [b"-1.5"], [b"-.5"], ["-٣".encode()], [b"-5\n"],
    [b"-5\n\n"], [b"-x y"], [b"-x.txt"], [b""], [b"basic.txt/"], [b"basic.txt/."], [b"./basic.txt"],
    [b".//basic.txt"], [b"adir/"], [b"nope/"], [b"basic.txt/x"], [b"--=x"], [b"---x"], [b"--", b"--"],
    [b"--"], [B, b"--"], [B, b"--", b"--json"], [b"--", B, b"--json"], [b"--json", b"--", B],
    [b"--json", B, b"--"], [B, b"--top", b" 3"], [B, b"--top", b"3 "], [B, b"--top", "٣".encode()],
    [B, b"--top", b"9" * 5000], [B, b"--top", b"999999999999999999"], [B, b"--top", b"1000000000000000000"],
    [B, b"--top", b"000"], [B, b"--top", b"007"], [B, b"--top", b""], [b" -5"], [b"-"], [b"bom.txt"],
    [b"ctrl.txt", b"--json"], [b"ctrl.txt"], [b"sigma.txt", b"--json"], [B, b"--top", b"\xff"],
    [B, b"--\xff"], [B, b"-\xff"], [B, b"\xff"], [b"-", b"-"], [B, b"--top", b"1", b"--json", b"--top", b"x"],
    [B, b"--top", b"1", b"--top", b"x", b"-h"], [b"--top", b"1"], [B, b"--json", b"--json"],
    [b"-t", B], [b"-j", B], [B, b"--top", b"\xef\xbc\x92"], [B, b"--top", b"1e3"], [B, b"--top", b"0x10"],
    [b"-1", B],
]


# 기준 구현이 인자 오류 메시지(UTF-8 이 아닌 바이트 포함)를 stderr 에 쓰다가 UnicodeEncodeError 로 멈추고 1로 끝나는 경우.
# 계약 4절(인자 오류는 2)을 따라 Rust 는 2로 끝낸다. reports/port_notes.md 참조
CONTRACT_OVER_REFERENCE = [
    [B, b"--top", b"\xff"], [B, b"--\xff"], [B, b"-\xff"], [B, b"\xff"],
]


def prepare(work: Path) -> None:
    (work / "basic.txt").write_text("the cat the hat\n", encoding="utf-8")
    (work / "adir").mkdir()
    (work / "-").write_text("dash file\n", encoding="utf-8")
    (work / "-5").write_text("five\n", encoding="utf-8")
    (work / "bom.txt").write_text("﻿hello hello\n", encoding="utf-8")
    (work / "ctrl.txt").write_bytes("a\x00b a\x08b a\x7fb a\"b a\\b a‎b a\x1cb a\x0bb 　x​y é e z \U0001F600 �\r\n".encode())
    (work / "sigma.txt").write_text("ΑΣ Σ ΑΣΑ ΑΣ'Β ΆΣ ΑΣ́ 'ΑΣ' İ ꟋA \U00010D50\n", encoding="utf-8")


def run(cmd: list[bytes], work: Path) -> tuple[int, bytes, bytes]:
    proc = subprocess.run(cmd, cwd=work, capture_output=True, timeout=60)
    return proc.returncode, proc.stdout, proc.stderr


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rust", type=Path, default=ROOT / "rust_app" / "target" / "release" / "wordfreq")
    parser.add_argument("--show", action="store_true", help="print the reference result of every case")
    args = parser.parse_args()
    binary = os.fsencode(args.rust.resolve())
    fails = 0
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        prepare(work)
        for case in CASES:
            py = run([os.fsencode(sys.executable), os.fsencode(REFERENCE), *case], work)
            rs = run([binary, *case], work)
            if case in CONTRACT_OVER_REFERENCE:
                ok = py[0] == 1 and b"UnicodeEncodeError" in py[2] and rs[0] == 2 and bool(rs[2])
            elif py[0] == 2:
                ok = rs[0] == 2 and bool(rs[2])
            else:
                ok = py == rs
            fails += not ok
            if args.show or not ok:
                print(f"{'OK  ' if ok else 'FAIL'} {case!r}")
                print(f"     python: {py[0]} {py[1][:120]!r} {py[2][-160:]!r}")
                print(f"     rust:   {rs[0]} {rs[1][:120]!r} {rs[2][-160:]!r}")
    print(f"{len(CASES) - fails}/{len(CASES)} argument cases match")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
