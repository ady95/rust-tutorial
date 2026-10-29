"""서버별 부하 측정 (10-4). 서버를 띄우고 상품 1,000개를 넣은 뒤, 요청 종류마다 load.py 로 부하를 준다.

사용법: python3 run_load.py --name py --out results/py.json -- <서버 실행 명령...>   (서버는 --port 를 받아야 한다)
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from race import free_port  # noqa: E402

WORKLOADS = [
    # (이름, 메서드, 경로, 본문, 프로세스 수, 프로세스당 연결 수)
    ("health", "GET", "/health", "", 4, 16),
    ("get_item", "GET", "/items/500", "", 4, 16),
    ("list_20", "GET", "/items?limit=20&offset=100", "", 4, 16),
    ("reserve", "POST", "/items/1/reserve", '{"quantity":1}', 4, 16),
    ("get_item_1conn", "GET", "/items/500", "", 1, 1),
]


def http(port: int, method: str, path: str, body: str = "") -> int:
    import http.client

    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    conn.request(method, path, body=body.encode() or None, headers={"Content-Type": "application/json"} if body else {})
    status = conn.getresponse().status
    conn.close()
    return status


def rss_kb(pid: int) -> int:
    for line in Path(f"/proc/{pid}/status").read_text().splitlines():
        if line.startswith("VmRSS:"):
            return int(line.split()[1])
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", required=True)
    parser.add_argument("--duration", type=float, default=10.0)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("cmd", nargs="+")
    args = parser.parse_args()
    port = free_port()
    started = time.perf_counter()
    proc = subprocess.Popen([*args.cmd, "--port", str(port)], env=dict(os.environ, STOCKROOM_TEST="1"),
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        while True:  # 첫 /health 응답까지의 시간 = 시작 시간
            try:
                if http(port, "GET", "/health") == 200:
                    break
            except OSError:
                time.sleep(0.005)
        startup_ms = (time.perf_counter() - started) * 1000
        idle_rss = rss_kb(proc.pid)
        http(port, "POST", "/items", '{"name":"stock","price":1.5,"quantity":1000000}')
        for i in range(2, 1001):
            http(port, "POST", "/items", json.dumps({"name": f"item{i}", "price": i / 10, "quantity": i, "tags": ["t"]}))
        seeded_rss = rss_kb(proc.pid)
        results = {"name": args.name, "startup_ms": round(startup_ms, 1), "idle_rss_kb": idle_rss,
                   "rss_after_1000_items_kb": seeded_rss, "workloads": {}}
        for name, method, path, body, procs, conns in WORKLOADS:
            out = subprocess.run([sys.executable, str(HERE / "load.py"), "--port", str(port), "--pid", str(proc.pid),
                                  "--method", method, "--path", path, "--body", body, "--procs", str(procs),
                                  "--conns", str(conns), "--duration", str(args.duration)],
                                 capture_output=True, text=True, check=True)
            results["workloads"][name] = json.loads(out.stdout.strip().splitlines()[-1])
            r = results["workloads"][name]
            print(f"{args.name:<8}{name:<16}{r['rps']:>10,.0f} rps  p50 {r['latency_ms']['p50']:7.2f}  "
                  f"p99 {r['latency_ms']['p99']:7.2f} ms  cpu {r['server_cpu_us_per_request']:7.1f} us/req  "
                  f"rss {r['server_max_rss_kb'] / 1024:6.1f} MB  err {r['errors']}")
    finally:
        proc.terminate()
        proc.wait(timeout=5)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    print(f"{args.name}: startup {results['startup_ms']} ms, idle RSS {idle_rss / 1024:.1f} MB, "
          f"after 1000 items {seeded_rss / 1024:.1f} MB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
