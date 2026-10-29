"""기존 비교 도구에 없는 명령행 입력(위험 R3, R4, R5, R7, R12, open_questions)을 기준 구현으로 실행하고,
--rust 를 주면 Rust 실행 파일과도 비교한다.

판정:
  - Python 종료 코드가 2 이면 인자 오류: 종료 코드 2 와 stderr 비어 있지 않음만 비교 (계약 4절)
  - contract_code 가 있는 케이스: 기준 구현이 계약과 다른 지점. Rust 는 계약 값을 내야 하고 stderr 는 비교 안 함
  - help 케이스: 종료 코드 0 과 stdout 비어 있지 않음만 비교 (도움말 문구는 계약 밖)
  - 그 밖: 종료 코드, stdout, stderr 바이트 비교

사용법 (프로젝트 루트에서): python3 verify/probe_cli.py [--rust rust_app/target/release/wordfreq] [--show]
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REFERENCE = ROOT / "python_src" / "wordfreq.py"
B = b"tests/fixtures/basic.txt"
T = b"tests/fixtures/ties.txt"

# (이름, 인자, 규칙) 규칙: "auto" | "help" | ("contract", 코드)
CASES: list[tuple[str, list[bytes], object]] = [
    # R4: argparse 문법
    ("abbrev-to", [B, b"--to", b"2"], "auto"),
    ("abbrev-t", [B, b"--t", b"2"], "auto"),
    ("abbrev-js", [B, b"--js"], "auto"),
    ("abbrev-j", [B, b"--j"], "auto"),
    ("abbrev-t-equals", [B, b"--t=2"], "auto"),
    ("abbrev-to-equals", [B, b"--to=2"], "auto"),
    ("top-equals-empty", [B, b"--top="], "auto"),
    ("top-zero-then-two", [B, b"--top", b"0", b"--top", b"2"], "auto"),
    ("top-two-then-zero", [B, b"--top", b"2", b"--top", b"0"], "auto"),
    ("top-before-file", [b"--top", b"2", B], "auto"),
    ("json-before-file", [b"--json", B], "auto"),
    ("json-twice", [B, b"--json", b"--json"], "auto"),
    ("two-files", [B, T], "auto"),
    ("json-equals", [B, b"--json=1"], "auto"),
    ("json-equals-empty", [B, b"--json="], "auto"),
    ("top-missing-value", [B, b"--top"], "auto"),
    ("top-value-is-option", [B, b"--top", b"--json"], "auto"),
    ("top-value-is-dashdash", [B, b"--top", b"--", b"2"], "auto"),
    ("top-negative", [B, b"--top", b"-1"], "auto"),
    ("top-space-before", [B, b"--top", b" 3"], "auto"),
    ("top-space-after", [B, b"--top", b"3 "], "auto"),
    ("top-empty", [B, b"--top", b""], "auto"),
    ("top-000", [B, b"--top", b"000"], "auto"),
    ("top-arabic", [B, b"--top", "٣".encode()], "auto"),
    ("top-18-digits", [B, b"--top", b"999999999999999999"], "auto"),
    ("top-19-digits", [B, b"--top", b"1000000000000000000"], "auto"),
    ("top-5000-digits", [B, b"--top", b"9" * 5000], "auto"),
    ("top-1", [B, b"--top", b"1"], "auto"),
    ("dashdash-x", [b"--", b"-x"], "auto"),
    ("dashdash-only", [b"--"], "auto"),
    ("dashdash-dashdash", [b"--", b"--"], "auto"),
    ("dashdash-file-extra", [b"--", B, b"--json"], "auto"),
    ("json-dashdash-file", [b"--json", b"--", B], "auto"),
    ("file-dashdash", [B, b"--"], "auto"),
    ("file-json-dashdash", [B, b"--json", b"--"], "auto"),
    ("file-dashdash-dashdash", [B, b"--", b"--"], "auto"),
    ("neg-int", [b"-5"], "auto"),
    ("neg-float", [b"-1.5"], "auto"),
    ("neg-dotfloat", [b"-.5"], "auto"),
    ("neg-arabic", ["-٣".encode()], "auto"),
    ("neg-fullwidth", ["-５".encode()], "auto"),
    ("neg-newline", [b"-5\n"], "auto"),
    ("neg-two-newlines", [b"-5\n\n"], "auto"),
    ("neg-5x", [b"-5x"], "auto"),
    ("neg-and-file", [B, b"-5"], "auto"),
    ("dash-space", [b"- x"], "auto"),
    ("dashdash-space", [b"--foo bar"], "auto"),
    ("dash-x-txt", [b"-x.txt"], "auto"),
    ("dashdashdash", [B, b"---"], "auto"),
    ("dashdash-equals", [B, b"--=x"], "auto"),
    ("unknown-then-help", [b"--bogus", b"-h"], "help"),
    ("help-short", [b"-h"], "help"),
    ("help-long", [b"--help"], "help"),
    ("help-abbrev", [b"--he"], "help"),
    ("help-abbrev-h", [b"--h"], "help"),
    ("help-hh", [b"-hh"], "help"),
    ("help-hfoo", [b"-hfoo"], "help"),
    ("help-h-dash", [b"-h-x"], "auto"),
    ("help-h-equals", [b"-h=x"], "auto"),
    ("help-equals", [b"--help=x"], "auto"),
    ("help-after-file", [B, b"-h"], "help"),
    ("top-error-then-help", [B, b"--top", b"0", b"-h"], "auto"),
    ("help-then-top-error", [b"-h", B, b"--top", b"0"], "help"),
    ("no-args", [], "auto"),
    # R5: pathlib 정규화
    ("path-trailing-slash", [B + b"/"], "auto"),
    ("path-trailing-dot", [B + b"/."], "auto"),
    ("path-inner-dot", [b"tests/fixtures/./basic.txt"], "auto"),
    ("path-leading-dot", [b"./tests//fixtures/basic.txt"], "auto"),
    ("path-empty", [b""], "auto"),
    ("path-fixtures-slash", [b"tests/fixtures/"], "auto"),
    ("path-missing-slash", [b"nope.txt/"], "auto"),
    ("path-enotdir", [B + b"/x"], "auto"),
    ("path-dot", [b"."], "auto"),
    ("path-dotdot", [b"tests/fixtures/../fixtures/basic.txt"], "auto"),
    ("path-too-long", [b"a" * 300], "auto"),
    # R12: UTF-8 이 아닌 옵션 값 / 모르는 옵션 / 남는 위치 인자
    ("r12-top-ff", [B, b"--top", b"\xff"], ("contract", 2)),
    ("r12-option-ff", [B, b"--\xff"], ("contract", 2)),
    ("r12-extra-ff", [B, b"\xff"], ("contract", 2)),
    ("r12-top-equals-ff", [B, b"--top=\xff"], ("contract", 2)),
]


def run(cmd: list[bytes]) -> tuple[int, bytes, bytes]:
    proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, timeout=60)
    return proc.returncode, proc.stdout, proc.stderr


def judge(rule: object, py: tuple[int, bytes, bytes], rs: tuple[int, bytes, bytes]) -> list[str]:
    if isinstance(rule, tuple):
        code = rule[1]
        return [] if rs[0] == code and rs[2] else [f"contract code {code} expected, rust={rs[0]}"]
    if rule == "help":
        problems = []
        if py[0] != 0 or rs[0] != 0:
            problems.append(f"help exit: python={py[0]} rust={rs[0]}")
        if not rs[1]:
            problems.append("help: rust stdout empty")
        if py[1] != rs[1]:
            problems.append("help: text differs (계약 밖이지만 기록)")
        return problems
    problems = []
    if py[0] != rs[0]:
        problems.append(f"exit: python={py[0]} rust={rs[0]}")
    if py[0] == 2:
        if not rs[2]:
            problems.append("usage: rust stderr empty")
        if rs[1]:
            problems.append("usage: rust stdout not empty")
        return problems
    if py[1] != rs[1]:
        problems.append(f"stdout: python={py[1][:120]!r} rust={rs[1][:120]!r}")
    if py[2] != rs[2]:
        problems.append(f"stderr: python={py[2][-200:]!r} rust={rs[2][-200:]!r}")
    return problems


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rust", type=Path)
    parser.add_argument("--show", action="store_true", help="print python stdout/stderr")
    args = parser.parse_args()
    failed = 0
    for name, cmd_args, rule in CASES:
        py = run([os.fsencode(sys.executable), os.fsencode(REFERENCE), *cmd_args])
        line = f"{name:24} py={py[0]}"
        if args.show:
            line += f" out={py[1][:100]!r} err={py[2][-160:]!r}"
        if args.rust:
            rs = run([os.fsencode(args.rust.resolve()), *cmd_args])
            problems = judge(rule, py, rs)
            line = ("OK   " if not problems else "FAIL ") + line + f" rs={rs[0]}"
            failed += bool(problems)
            print(line)
            for p in problems:
                print("     " + p)
        else:
            print(line)
    if args.rust:
        print(f"\n{len(CASES) - failed}/{len(CASES)} probe cases match")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
