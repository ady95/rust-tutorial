"""정해 둔 요청열(tests/cases.json)로 기준 구현 서버와 Rust 서버를 비교한다 (계약 4절의 규칙).

사용법 (프로젝트 루트에서): uv run python automation/compare.py [--rust rust_app/target/release/stockroom]
종료 코드: 0 = 모두 같음, 1 = 다름, 2 = Rust 실행 파일 없음, 3 = 서버를 띄우지 못함
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from http_diff import ROOT, run_steps, start_pair  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare the Python and Rust stockroom servers.")
    parser.add_argument("--rust", type=Path, default=ROOT / "rust_app" / "target" / "release" / "stockroom")
    parser.add_argument("--cases", type=Path, default=ROOT / "tests" / "cases.json")
    args = parser.parse_args()
    if not args.rust.exists():
        print(f"Rust binary not found: {args.rust}", file=sys.stderr)
        return 2
    cases = json.loads(args.cases.read_text(encoding="utf-8"))
    try:
        python, rust = start_pair(args.rust)
    except RuntimeError as err:
        print(f"ERROR {err}", file=sys.stderr)
        return 3
    failed = 0
    try:
        for case in cases:
            problems = run_steps(python, rust, case["steps"])
            failed += bool(problems)
            print(f"{'OK  ' if not problems else 'FAIL'} {case['name']}")
            for problem in problems:
                print(f"     {problem}")
    finally:
        python.stop()
        rust.stop()
    print(f"\n{len(cases) - failed}/{len(cases)} cases match")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
