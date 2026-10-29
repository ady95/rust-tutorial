"""JSON 중첩 한도(RecursionError → 400)를 두 서버에서 이분 탐색으로 찾아 비교한다.

사용법: uv run python verify/probe_depth.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "automation"))

from http_diff import start_pair  # noqa: E402


ROUTES = [("POST", "/items", "name"), ("PATCH", "/items/1", "name"), ("POST", "/items/1/reserve", "quantity")]
ROUTE = ROUTES[0]


def status(server, depth: int, opener: str) -> int:
    method, path, field = ROUTE
    inner = "[" * depth + "]" * depth if opener == "[" else '{"a":' * depth + "1" + "}" * depth
    body = ('{"' + field + '":' + inner + "}").encode()
    return server.request(method, path, body, {"Content-Type": "application/json"})[0]


def boundary(server, opener: str) -> int:
    """422 가 나오는 가장 큰 깊이"""
    lo, hi = 1, 20000
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if status(server, mid, opener) == 422:
            lo = mid
        else:
            hi = mid - 1
    return lo


def main() -> int:
    python, rust = start_pair(ROOT / "rust_app" / "target" / "release" / "stockroom")
    global ROUTE
    try:
        for ROUTE in ROUTES:
            for opener in "[{":
                p, r = boundary(python, opener), boundary(rust, opener)
                print(f"{ROUTE[0]} {ROUTE[1]} {opener} python={p} rust={r} "
                      f"next: python={status(python, p + 1, opener)} rust={status(rust, r + 1, opener)}")
    finally:
        python.stop()
        rust.stop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
