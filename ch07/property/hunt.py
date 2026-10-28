"""입력 생성 전략별로 Rust 구현이 Python 과 다른 입력을 몇 번 만에 찾는지 잰다 (07-2).

사용법 (ch07/property 에서):
    uv run python hunt.py <Rust 실행 파일> [--strategy any_text] [--seeds 1 2 3] [--max-examples 2000]

출력(JSON 한 줄씩): 실행 파일, 전략, seed, 찾았는지, 처음 찾은 예제 번호, 걸린 시간, 줄인(shrink) 최소 입력
"""

import argparse
import json
import sys
import time
from pathlib import Path

from hypothesis import HealthCheck, given, seed, settings
from hypothesis import strategies as st

from equivalence import STRATEGIES, compare


def hunt(binary: Path, strategy_name: str, seed_value: int, max_examples: int) -> dict:
    state = {"n": 0, "first": None, "last": None}

    @seed(seed_value)
    @settings(max_examples=max_examples, database=None, deadline=None, suppress_health_check=list(HealthCheck))
    @given(text=STRATEGIES[strategy_name], top=st.integers(1, 20), as_json=st.booleans())
    def prop(text: str, top: int, as_json: bool) -> None:
        state["n"] += 1
        exp, got = compare(binary, text, top, as_json)
        if exp != got:
            if state["first"] is None:
                state["first"] = state["n"]
            state["last"] = {"text": text, "top": top, "json": as_json, "rust_exit": got[1]}
            raise AssertionError("output differs")

    start = time.perf_counter()
    try:
        prop()
        found = False
    except AssertionError:
        found = True
    return {
        "binary": binary.name,
        "strategy": strategy_name,
        "seed": seed_value,
        "found": found,
        "first_failure_at": state["first"],
        "examples_run": state["n"],
        "seconds": round(time.perf_counter() - start, 1),
        # Hypothesis 는 실패를 찾으면 입력을 줄여 가며 다시 실행한다. 마지막 실패가 가장 작은 입력이다
        "minimal": state["last"],
        "minimal_codepoints": [f"U+{ord(c):04X}" for c in state["last"]["text"]] if state["last"] else None,
    }


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser()
    parser.add_argument("binary", type=Path)
    parser.add_argument("--strategy", choices=list(STRATEGIES), action="append")
    parser.add_argument("--seeds", type=int, nargs="+", default=[1, 2, 3])
    parser.add_argument("--max-examples", type=int, default=2000)
    args = parser.parse_args()
    for name in args.strategy or list(STRATEGIES):
        for s in args.seeds:
            print(json.dumps(hunt(args.binary.resolve(), name, s, args.max_examples), ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
