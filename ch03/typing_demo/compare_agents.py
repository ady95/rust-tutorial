"""Python 원본(loose/strict)과 에이전트가 만든 Rust 결과를 같은 입력으로 비교한다 (03-1).

사용법 (ch03/typing_demo 에서):
    uv run --no-project python compare_agents.py <loose|strict> <Rust 실행 파일>
"""

import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def run(cmd: list[str]) -> tuple[int, bytes]:
    proc = subprocess.run(cmd, cwd=HERE, capture_output=True, timeout=30)
    return proc.returncode, proc.stdout


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    version, rust_exe = sys.argv[1], str(Path(sys.argv[2]).resolve())
    same = 0
    cases = sorted((HERE / "cases").glob("*.json"))
    for case in cases:
        py = run([sys.executable, f"{version}.py", str(case)])
        rs = run([rust_exe, str(case)])
        ok = py == rs
        same += ok
        print(f"{'same' if ok else 'DIFF'}  {case.stem:<18} python={py}  rust={rs}")
    print(f"\n{same}/{len(cases)} same")
    return 0


if __name__ == "__main__":
    sys.exit(main())
