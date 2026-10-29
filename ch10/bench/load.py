"""간단한 HTTP/1.1 부하 생성기 (10-4). 표준 라이브러리만 쓴다.

여러 프로세스가 각자 asyncio 로 연결 여러 개를 열고, 연결마다 keep-alive 로 요청을 차례로 보낸다(닫힌 루프).
지연시간 분포와 처리량을 내고, 서버 프로세스의 CPU 시간·최대 메모리를 /proc 에서 읽어 요청당 CPU 시간을 계산한다.
클라이언트가 Python 이라 아주 빠른 서버에서는 클라이언트가 먼저 한계에 닿을 수 있다. 그래서 요청당 서버 CPU 시간도 함께 본다.

사용법: python3 load.py --port 8000 --pid <서버 PID> --path /items/1 [--procs 4 --conns 16 --duration 10]
        python3 load.py ... --method POST --path /items --body '{"name":"a","price":1,"quantity":1}'
"""

from __future__ import annotations

import argparse
import asyncio
import json
import multiprocessing as mp
import os
import statistics
import time
from pathlib import Path

CLK = os.sysconf("SC_CLK_TCK")


def cpu_seconds(pid: int) -> float:
    fields = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()
    return (int(fields[11]) + int(fields[12])) / CLK  # utime + stime


def max_rss_kb(pid: int) -> int:
    for line in Path(f"/proc/{pid}/status").read_text().splitlines():
        if line.startswith("VmHWM:"):
            return int(line.split()[1])
    return 0


async def one_connection(port: int, request: bytes, deadline: float, latencies: list[int], errors: list[int]) -> None:
    reader, writer = await asyncio.open_connection("127.0.0.1", port)
    try:
        while time.perf_counter() < deadline:
            start = time.perf_counter_ns()
            writer.write(request)
            head = await reader.readuntil(b"\r\n\r\n")
            status = int(head[9:12])
            length = 0
            for line in head.split(b"\r\n")[1:]:
                if line[:15].lower() == b"content-length:":
                    length = int(line[15:])
            if length:
                await reader.readexactly(length)
            latencies.append(time.perf_counter_ns() - start)
            if status >= 400:
                errors.append(status)
    finally:
        writer.close()


def worker(port: int, request: bytes, conns: int, duration: float, start_at: float, out: mp.Queue) -> None:
    async def run() -> tuple[list[int], list[int]]:
        while time.time() < start_at:  # 모든 프로세스가 같은 순간에 시작
            await asyncio.sleep(0.001)
        latencies: list[int] = []
        errors: list[int] = []
        deadline = time.perf_counter() + duration
        await asyncio.gather(*(one_connection(port, request, deadline, latencies, errors) for _ in range(conns)))
        return latencies, errors

    out.put(asyncio.run(run()))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--pid", type=int, required=True, help="서버 프로세스 PID (CPU·메모리 측정용)")
    parser.add_argument("--method", default="GET")
    parser.add_argument("--path", default="/items/1")
    parser.add_argument("--body", default="")
    parser.add_argument("--procs", type=int, default=4)
    parser.add_argument("--conns", type=int, default=16, help="프로세스당 연결 수")
    parser.add_argument("--duration", type=float, default=10.0)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()

    body = args.body.encode()
    request = (f"{args.method} {args.path} HTTP/1.1\r\nHost: 127.0.0.1:{args.port}\r\n"
               + (f"Content-Type: application/json\r\nContent-Length: {len(body)}\r\n" if body else "")
               + "\r\n").encode() + body
    queue: mp.Queue = mp.Queue()
    start_at = time.time() + 0.5
    cpu_before = cpu_seconds(args.pid)
    procs = [mp.Process(target=worker, args=(args.port, request, args.conns, args.duration, start_at, queue))
             for _ in range(args.procs)]
    for p in procs:
        p.start()
    results = [queue.get() for _ in procs]
    for p in procs:
        p.join()
    cpu_used = cpu_seconds(args.pid) - cpu_before
    latencies = sorted(x for lat, _ in results for x in lat)
    errors = sum(len(err) for _, err in results)
    n = len(latencies)

    def pct(p: float) -> float:
        return latencies[min(n - 1, int(p / 100 * n))] / 1e6

    report = {
        "request": f"{args.method} {args.path}", "connections": args.procs * args.conns, "duration_s": args.duration,
        "requests": n, "errors": errors, "rps": n / args.duration,
        "latency_ms": {"p50": pct(50), "p90": pct(90), "p99": pct(99), "max": latencies[-1] / 1e6,
                       "mean": statistics.fmean(latencies) / 1e6},
        "server_cpu_s": cpu_used, "server_cpu_us_per_request": cpu_used / n * 1e6, "server_max_rss_kb": max_rss_kb(args.pid),
    }
    print(json.dumps(report))
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
