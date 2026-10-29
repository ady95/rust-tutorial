"""무작위 정수·실수 문자열을 경로(item_id)·쿼리(limit)·본문(quantity, price)으로 두 서버에 보내 비교한다.

사용법: uv run python verify/diff_ints.py [개수]
"""

from __future__ import annotations

import random
import sys
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "automation"))
sys.path.insert(0, str(ROOT / "verify"))

from http_diff import run_steps, start_pair  # noqa: E402
from int_model import TOKENS  # noqa: E402

EXTRA = ["e", "E", "inf", "nan", " ", "\t", "\n", ".5", "1."]


def sample(rng: random.Random) -> str:
    return "".join(rng.choice(TOKENS + EXTRA) for _ in range(rng.randint(0, 7)))


def main() -> int:
    count = int(sys.argv[1]) if len(sys.argv) > 1 else 2000
    rng = random.Random(11)
    python, rust = start_pair(ROOT / "rust_app" / "target" / "release" / "stockroom")
    bad = 0
    try:
        for batch in range(count // 50):
            steps = [{"method": "POST", "path": "/items", "json": {"name": "a", "price": 1, "quantity": 1}}]
            for _ in range(50):
                s = sample(rng)
                steps += [{"method": "GET", "path": "/items/" + quote(s, safe="")},
                          {"method": "GET", "path": "/items?limit=" + quote(s, safe="")},
                          {"method": "POST", "path": "/items", "json": {"name": "a", "price": s, "quantity": s}}]
            problems = run_steps(python, rust, steps)
            if problems:
                bad += 1
                print(f"batch {batch}: " + " | ".join(p[:200] for p in problems))
    finally:
        python.stop()
        rust.stop()
    print(f"{count // 50 - bad}/{count // 50} batches match")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
