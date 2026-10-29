"""Python 기준 구현(stats)과 Rust 구현을 같은 입력으로 실행해 결과를 비교한다.

사용법 (프로젝트 루트에서):
    uv run python automation/compare.py
    uv run python automation/compare.py --rust rust_app/target/release/stats.exe

비교 항목: stdout(바이트), stderr(바이트), 종료 코드.
cases.json 에서 stderr_ignored 가 true 인 케이스는 계약 4절에 따라
종료 코드와 stdout 만 비교한다.

종료 코드: 0 = 모두 일치, 1 = 불일치 있음, 2 = Rust 실행 파일 없음,
3 = 프로그램을 실행하지 못함(운영체제 정책 차단 등). 3 은 코드 문제가 아니다.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


@dataclass
class Run:
    code: int
    out: bytes
    err: bytes


class LaunchError(Exception):
    """프로그램을 아예 실행하지 못했다 (출력 비교 이전의 문제)."""


def run(cmd: list[str]) -> Run:
    try:
        proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, timeout=30)
    except OSError as err:  # Windows 스마트 앱 컨트롤 차단(WinError 4551) 등
        raise LaunchError(f"{cmd[0]}: {err}") from err
    return Run(proc.returncode, proc.stdout, proc.stderr)


def default_rust_binary() -> Path:
    name = "stats.exe" if sys.platform == "win32" else "stats"
    return ROOT / "rust_app" / "target" / "release" / name


def compare(case: dict, py: Run, rs: Run) -> list[str]:
    problems = []
    if py.code != rs.code:
        problems.append(f"exit code: python={py.code} rust={rs.code}")
    if py.out != rs.out:
        problems.append(f"stdout: python={py.out!r} rust={rs.out!r}")
    if not case.get("stderr_ignored") and py.err != rs.err:
        problems.append(f"stderr: python={py.err!r} rust={rs.err!r}")
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare Python and Rust stats.")
    parser.add_argument("--rust", type=Path, default=default_rust_binary())
    parser.add_argument("--cases", type=Path, default=ROOT / "tests" / "cases.json")
    parser.add_argument("--report", type=Path, help="write JSON result to this file")
    args = parser.parse_args()

    if not args.rust.exists():
        print(f"Rust binary not found: {args.rust}", file=sys.stderr)
        return 2

    python_cmd = [sys.executable, "python_src/stats.py"]
    rust_cmd = [str(args.rust.resolve())]
    cases = json.loads(args.cases.read_text(encoding="utf-8"))

    results = []
    for case in cases:
        try:
            problems = compare(case, run(python_cmd + case["args"]), run(rust_cmd + case["args"]))
        except LaunchError as err:
            print(f"ERROR {case['name']}: could not run program", file=sys.stderr)
            print(f"     {err}", file=sys.stderr)
            return 3
        results.append({"name": case["name"], "ok": not problems, "problems": problems})
        print(f"{'OK  ' if not problems else 'FAIL'} {case['name']}")
        for problem in problems:
            print(f"     {problem}")

    passed = sum(r["ok"] for r in results)
    print(f"\n{passed}/{len(results)} cases match")
    if args.report:
        args.report.write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
