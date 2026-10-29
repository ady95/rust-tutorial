"""Rust 서버에 동시 예약을 보내 확인·차감이 원자적인지 본다(계약 5절).

사용법: uv run python verify/concurrency.py
"""

from __future__ import annotations

import http.client
import json
import sys
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "automation"))

from http_diff import start  # noqa: E402

STOCK, THREADS, PER_THREAD = 1000, 40, 40


def main() -> int:
    server = start("rust", [str(ROOT / "rust_app" / "target" / "release" / "stockroom")])
    try:
        body = json.dumps({"name": "c", "price": 1, "quantity": STOCK})
        assert server.request("POST", "/items", body.encode(), {"Content-Type": "application/json"})[0] == 201
        counts = {200: 0, 409: 0}
        lock = threading.Lock()

        def worker() -> None:
            conn = http.client.HTTPConnection("127.0.0.1", server.port, timeout=30)
            for _ in range(PER_THREAD):
                conn.request("POST", "/items/1/reserve", body=b'{"quantity":1}', headers={"Content-Type": "application/json"})
                response = conn.getresponse()
                response.read()
                with lock:
                    counts[response.status] = counts.get(response.status, 0) + 1
            conn.close()

        threads = [threading.Thread(target=worker) for _ in range(THREADS)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        remaining = json.loads(server.request("GET", "/items/1", None, {})[2])["quantity"]
        print(f"responses={counts} remaining={remaining}")
        ok = counts.get(200) == STOCK and remaining == 0 and counts.get(409) == THREADS * PER_THREAD - STOCK
        print("OK" if ok else "FAIL")
        return 0 if ok else 1
    finally:
        server.stop()


if __name__ == "__main__":
    sys.exit(main())
