"""동시 요청 시험 (10-4). 계약 5절: 같은 Item 에 대한 동시 예약의 합이 처음 수량을 넘지 않는다.

1) 수량 Q 인 Item 하나에 1개씩 예약하는 요청 N 개를 연결 C 개로 동시에 보낸다 → 성공 수가 정확히 min(N, Q), 남은 수량 Q - 성공 수
2) Item 생성 요청 M 개를 동시에 보낸다 → id 가 1..M 으로 겹치지 않고 빠짐없이

사용법: python3 race.py -- <서버 실행 명령...>          (서버는 --port 를 받아야 한다)
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import socket
import subprocess
import time


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


async def request(port: int, method: str, path: str, body: dict | None = None) -> tuple[int, dict]:
    reader, writer = await asyncio.open_connection("127.0.0.1", port)
    data = json.dumps(body).encode() if body is not None else b""
    head = f"{method} {path} HTTP/1.1\r\nHost: x\r\nConnection: close\r\n"
    if body is not None:
        head += f"Content-Type: application/json\r\nContent-Length: {len(data)}\r\n"
    writer.write(head.encode() + b"\r\n" + data)
    raw = await reader.read()
    writer.close()
    header, _, payload = raw.partition(b"\r\n\r\n")
    return int(header[9:12]), json.loads(payload) if payload else {}


async def scenario(port: int, total: int, quantity: int, conns: int, creates: int) -> dict:
    await request(port, "POST", "/_test/reset")
    _, item = await request(port, "POST", "/items", {"name": "r", "price": 1, "quantity": quantity})
    gate = asyncio.Semaphore(conns)

    async def reserve() -> int:
        async with gate:
            return (await request(port, "POST", f"/items/{item['id']}/reserve", {"quantity": 1}))[0]

    started = time.perf_counter()
    statuses = await asyncio.gather(*(reserve() for _ in range(total)))
    elapsed = time.perf_counter() - started
    _, after = await request(port, "GET", f"/items/{item['id']}")
    ok = statuses.count(200)

    async def create() -> int:
        async with gate:
            return (await request(port, "POST", "/items", {"name": "c", "price": 1, "quantity": 1}))[1]["id"]

    ids = sorted(await asyncio.gather(*(create() for _ in range(creates))))
    return {
        "reserve_requests": total, "initial_quantity": quantity, "succeeded": ok, "conflicts": statuses.count(409),
        "other_status": len(statuses) - ok - statuses.count(409), "remaining": after["quantity"],
        "reserve_ok": ok == min(total, quantity) and after["quantity"] == quantity - ok,
        "create_ids_ok": ids == list(range(item["id"] + 1, item["id"] + 1 + creates)), "seconds": round(elapsed, 3),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--requests", type=int, default=2000)
    parser.add_argument("--quantity", type=int, default=500)
    parser.add_argument("--conns", type=int, default=64)
    parser.add_argument("--creates", type=int, default=500)
    parser.add_argument("--repeat", type=int, default=5)
    parser.add_argument("cmd", nargs="+")
    args = parser.parse_args()
    port = free_port()
    proc = subprocess.Popen([*args.cmd, "--port", str(port)], env=dict(os.environ, STOCKROOM_TEST="1"),
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(200):
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=0.1):
                    break
            except OSError:
                time.sleep(0.05)
        results = [asyncio.run(scenario(port, args.requests, args.quantity, args.conns, args.creates))
                   for _ in range(args.repeat)]
    finally:
        proc.terminate()
        proc.wait(timeout=5)
    for r in results:
        print(json.dumps(r))
    passed = all(r["reserve_ok"] and r["create_ids_ok"] for r in results)
    print(f"{'PASS' if passed else 'FAIL'} {sum(r['reserve_ok'] and r['create_ids_ok'] for r in results)}/{len(results)}")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
