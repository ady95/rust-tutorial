"""범용 CLI 비교 도구 (12-1). 작업 폴더의 .rustify/ 에 복사되어 게이트에서 실행된다.

    uv run python .rustify/compare_cli.py --rust rust_app/target/release/<이름>

tests/cases.json 의 케이스마다 Python 기준 구현(automation/port.json 의 python)과 Rust 실행 파일을
같은 인자·표준 입력으로 실행해 종료 코드, stdout, stderr 를 바이트 단위로 비교한다.

케이스 필드:
  name, args            필수
  stdin | stdin_hex     표준 입력(문자열은 UTF-8 로)
  stdout                "compare"(기본) | "ignore"
  stderr                "compare"(기본) | "ignore" | "nonempty"(Rust 쪽이 비어 있지 않은지만)

종료 코드: 0 모두 일치, 1 불일치, 2 실행 파일 없음, 3 프로그램을 실행하지 못함(코드 문제가 아님).
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class LaunchError(Exception):
    pass


def run(cmd: list[str], stdin: bytes) -> tuple[int, bytes, bytes]:
    try:
        proc = subprocess.run(cmd, cwd=ROOT, input=stdin, capture_output=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired) as err:
        raise LaunchError(f"{cmd[0]}: {err}") from err
    return proc.returncode, proc.stdout, proc.stderr


def stdin_of(case: dict) -> bytes:
    if "stdin_hex" in case:
        return bytes.fromhex(case["stdin_hex"])
    return case.get("stdin", "").encode("utf-8")


def compare(case: dict, py: tuple[int, bytes, bytes], rs: tuple[int, bytes, bytes]) -> list[str]:
    problems = []
    if py[0] != rs[0]:
        problems.append(f"exit code: python={py[0]} rust={rs[0]}")
    if case.get("stdout", "compare") == "compare" and py[1] != rs[1]:
        problems.append(f"stdout: python={py[1][:300]!r} rust={rs[1][:300]!r}")
    rule = case.get("stderr", "compare")
    if rule == "compare" and py[2] != rs[2]:
        problems.append(f"stderr: python={py[2][:300]!r} rust={rs[2][:300]!r}")
    if rule == "nonempty" and not rs[2]:
        problems.append("stderr: rust printed nothing")
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare the Python reference and the Rust binary.")
    parser.add_argument("--rust", type=Path, required=True)
    parser.add_argument("--cases", type=Path, default=ROOT / "tests" / "cases.json")
    args = parser.parse_args()
    if not args.rust.exists():
        print(f"Rust binary not found: {args.rust}", file=sys.stderr)
        return 2
    manifest = json.loads((ROOT / "automation" / "port.json").read_text(encoding="utf-8"))
    python_cmd = [sys.executable, manifest["python"]]
    rust_cmd = [str(args.rust.resolve())]
    cases = json.loads(args.cases.read_text(encoding="utf-8"))
    passed = 0
    for case in cases:
        data = stdin_of(case)
        try:
            problems = compare(case, run(python_cmd + case["args"], data), run(rust_cmd + case["args"], data))
        except LaunchError as err:
            print(f"ERROR {case['name']}: {err}", file=sys.stderr)
            return 3
        passed += not problems
        print(f"{'OK  ' if not problems else 'FAIL'} {case['name']}")
        for problem in problems:
            print(f"     {problem}")
    print(f"\n{passed}/{len(cases)} cases match")
    return 0 if passed == len(cases) else 1


if __name__ == "__main__":
    sys.exit(main())
