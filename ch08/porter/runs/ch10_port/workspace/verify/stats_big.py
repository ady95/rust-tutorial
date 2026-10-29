"""stats 의 total_value 가 1e16 이상이 되는 경우(지수 표기)를 두 서버의 실제 응답으로 비교한다.

사용법: uv run python verify/stats_big.py
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "automation"))

from http_diff import start_pair  # noqa: E402

BODY = b'{"name":"big","price":1000000,"quantity":1000000}'


def main() -> int:
    python, rust = start_pair(ROOT / "rust_app" / "target" / "release" / "stockroom")
    try:
        for server in (python, rust):
            server.request("POST", "/_test/reset", None, {})
        results = {}
        for count in range(1, 10_001):
            for server in (python, rust):
                server.request("POST", "/items", BODY, {"Content-Type": "application/json"})
            if count in (9_999, 10_000):
                results[count] = [s.request("GET", "/stats", None, {})[2] for s in (python, rust)]
        for count, (p, r) in results.items():
            print(f"{count} items: python={p!r} rust={r!r} {'same' if p == r else 'DIFFERENT'}")
        return 0 if all(p == r for p, r in results.values()) else 1
    finally:
        python.stop()
        rust.stop()


if __name__ == "__main__":
    sys.exit(main())
