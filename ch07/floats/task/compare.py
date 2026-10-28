"""cases/ 의 입력 파일마다 Python 기준 구현과 Rust 구현을 실행해 stdout·stderr·종료 코드를 비교한다.

사용법 (이 폴더에서): python3 compare.py [--rust rust_app/target/release/stats]
종료 코드: 0 = 모두 같음, 1 = 다름, 2 = Rust 실행 파일 없음
"""

import argparse
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def run(cmd: list[str]) -> tuple[int, bytes, bytes]:
    proc = subprocess.run(cmd, cwd=HERE, capture_output=True, timeout=30)
    return proc.returncode, proc.stdout, proc.stderr


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rust", type=Path, default=HERE / "rust_app" / "target" / "release" / "stats")
    args = parser.parse_args()
    if not args.rust.exists():
        print(f"Rust binary not found: {args.rust}", file=sys.stderr)
        return 2
    cases = sorted((HERE / "cases").glob("*.txt"))
    failed = 0
    for case in cases:
        rel = str(case.relative_to(HERE))
        py = run([sys.executable, "python_src/stats.py", rel])
        rs = run([str(args.rust.resolve()), rel])
        ok = py == rs
        failed += not ok
        print(f"{'OK  ' if ok else 'FAIL'} {case.name}")
        if not ok:
            print(f"     python: {py!r}"[:300])
            print(f"     rust:   {rs!r}"[:300])
    print(f"\n{len(cases) - failed}/{len(cases)} cases match")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
