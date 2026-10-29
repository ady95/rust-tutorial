"""범용 무작위 비교 도구 (12-1). 작업 폴더의 .rustify/ 에 복사되어 게이트에서 실행된다.

    uv run python .rustify/fuzz_cli.py --rust rust_app/target/release/<이름> --examples 2000 --seed 7

입력 생성 규칙은 사람이 Python 으로 쓴 tests/strategies.py 의 cases() 가 정한다.
cases() 는 {"args": [...], "stdin": bytes} 를 만드는 Hypothesis 전략이다(선택: "stderr": "ignore").
종료 코드, stdout, stderr 를 바이트 단위로 비교하고, 다르면 Hypothesis 가 줄인 가장 작은 예를 보여 준다.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from hypothesis import HealthCheck, given, seed, settings

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests"))

import strategies  # noqa: E402


def run(cmd: list[str], stdin: bytes) -> tuple[int, bytes, bytes]:
    proc = subprocess.run(cmd, cwd=ROOT, input=stdin, capture_output=True, timeout=30)
    return proc.returncode, proc.stdout, proc.stderr


def main() -> int:
    parser = argparse.ArgumentParser(description="Random differential test of the Python reference and the Rust binary.")
    parser.add_argument("--rust", type=Path, required=True)
    parser.add_argument("--examples", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()
    manifest = json.loads((ROOT / "automation" / "port.json").read_text(encoding="utf-8"))
    python_cmd = [sys.executable, manifest["python"]]
    rust_cmd = [str(args.rust.resolve())]
    count = 0

    @seed(args.seed)
    @settings(max_examples=args.examples, deadline=None, database=None,
              suppress_health_check=list(HealthCheck))
    @given(strategies.cases())
    def same(case: dict) -> None:
        nonlocal count
        count += 1
        py = run(python_cmd + case["args"], case["stdin"])
        rs = run(rust_cmd + case["args"], case["stdin"])
        if case.get("stderr") == "ignore":
            py, rs = py[:2], rs[:2]
        assert py == rs, f"\nargs={case['args']!r}\nstdin={case['stdin'][:500]!r}\npython={py!r}\nrust={rs!r}"

    try:
        same()
    except AssertionError as err:
        print(f"FAIL (seed {args.seed}){err}")
        return 1
    print(f"{count} random cases match (seed {args.seed})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
