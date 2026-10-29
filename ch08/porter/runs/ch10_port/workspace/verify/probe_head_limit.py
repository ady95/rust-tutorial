"""기준 서버가 받는 요청 머리 크기의 경계를 이분 탐색한다(두 번 재서 안정한지 본다).

사용법: uv run python verify/probe_head_limit.py
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "automation"))
sys.path.insert(0, str(ROOT / "verify"))

from http_diff import start_pair  # noqa: E402
from http_raw import exchange, req  # noqa: E402


def accepted(port: int, size: int) -> bool:
    return exchange(port, req(headers=[b"X-A: " + b"a" * size]), False)[0] == 200


def boundary(port: int) -> int:
    lo, hi = 70000, 200000
    while lo < hi:
        mid = (lo + hi + 1) // 2
        lo, hi = (mid, hi) if accepted(port, mid) else (lo, mid - 1)
    return lo


python, rust = start_pair(ROOT / "rust_app" / "target" / "release" / "stockroom")
try:
    for name, server in (("python", python), ("python", python), ("rust", rust)):
        print(name, "largest accepted X-A value size:", boundary(server.port))
finally:
    python.stop()
    rust.stop()
