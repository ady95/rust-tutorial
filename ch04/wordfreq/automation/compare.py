"""Python 기준 구현과 Rust 구현을 같은 입력으로 실행해 결과를 비교한다.

사용법 (프로젝트 루트에서):
    uv run python automation/compare.py
    uv run python automation/compare.py --rust rust_app/target/release/wordfreq.exe

비교 항목: stdout(바이트), stderr(바이트), 종료 코드.
cases.json 에서 usage_error 가 true 인 케이스는 계약 4절에 따라
종료 코드와 "stderr 가 비어 있지 않음"만 비교한다.
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


def run(cmd: list[str]) -> Run:
    proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, timeout=30)
    return Run(proc.returncode, proc.stdout, proc.stderr)


def default_rust_binary() -> Path:
    name = "wordfreq.exe" if sys.platform == "win32" else "wordfreq"
    return ROOT / "rust_app" / "target" / "release" / name


def compare(case: dict, py: Run, rs: Run) -> list[str]:
    problems = []
    if py.code != rs.code:
        problems.append(f"exit code: python={py.code} rust={rs.code}")
    if case.get("usage_error"):
        if not rs.err:
            problems.append("stderr: rust printed nothing")
        return problems
    if py.out != rs.out:
        problems.append(f"stdout: python={py.out!r} rust={rs.out!r}")
    if py.err != rs.err:
        problems.append(f"stderr: python={py.err!r} rust={rs.err!r}")
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare Python and Rust wordfreq.")
    parser.add_argument("--rust", type=Path, default=default_rust_binary())
    parser.add_argument("--cases", type=Path, default=ROOT / "tests" / "cases.json")
    parser.add_argument("--report", type=Path, help="write JSON result to this file")
    args = parser.parse_args()

    if not args.rust.exists():
        print(f"Rust binary not found: {args.rust}", file=sys.stderr)
        return 2

    python_cmd = [sys.executable, "python_src/wordfreq.py"]
    rust_cmd = [str(args.rust.resolve())]
    cases = json.loads(args.cases.read_text(encoding="utf-8"))

    results = []
    for case in cases:
        problems = compare(case, run(python_cmd + case["args"]), run(rust_cmd + case["args"]))
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
