"""원시 소켓으로 HTTP 계층 세부(요청 줄·헤더 바이트, 본문 framing, 크기 한도)를 두 서버에 보내 비교한다.

비교: 상태 코드, Content-Type, Location, Allow, 본문(422 는 type·loc 만), 그리고 특수 케이스는 응답 뒤 연결을 닫는지.
사용법: uv run python verify/http_raw.py
"""

from __future__ import annotations

import json
import socket
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "automation"))

from http_diff import start_pair  # noqa: E402

GOOD = b'{"name":"a","price":1,"quantity":1}'
N = b"%x" % len(GOOD)


def exchange(port: int, data: bytes, check_close: bool) -> tuple:
    with socket.create_connection(("127.0.0.1", port), timeout=2) as sock:
        try:
            sock.sendall(data)
        except OSError:
            pass
        buf = b""
        try:
            while b"\r\n\r\n" not in buf:
                chunk = sock.recv(65536)
                if not chunk:
                    break
                buf += chunk
        except (TimeoutError, OSError):
            return ("no-response", buf[:60])
        if b"\r\n\r\n" not in buf:
            return ("no-response", buf[:60])
        head, _, body = buf.partition(b"\r\n\r\n")
        lines = head.split(b"\r\n")
        status = int(lines[0].split()[1])
        headers = {}
        for line in lines[1:]:
            k, _, v = line.partition(b":")
            headers[k.strip().lower().decode()] = v.strip().decode("latin-1")
        head_req = data.startswith(b"HEAD ")
        # content-length 가 없으면(uvicorn 의 400 등) 연결이 닫힐 때까지가 본문
        length = int(headers.get("content-length", str(1 << 30)))
        try:
            while not head_req and status != 204 and len(body) < length:
                chunk = sock.recv(65536)
                if not chunk:
                    break
                body += chunk
        except (TimeoutError, OSError):
            pass
        body = body[: 0 if head_req else length]
        if status == 422:
            try:
                body = repr([[e["type"], e["loc"]] for e in json.loads(body)["detail"]]).encode()
            except ValueError:
                pass
        closed = None
        if check_close:
            sock.settimeout(0.5)
            try:
                closed = sock.recv(1) == b""
            except (TimeoutError, OSError):
                closed = False
        loc = headers.get("location", "").replace(f"127.0.0.1:{port}", "<host>")
        return (status, headers.get("content-type"), loc, headers.get("allow"), body, closed)


def req(line: bytes = b"GET /health HTTP/1.1", headers: list[bytes] | None = None, body: bytes = b"",
        host: bool = True) -> bytes:
    hs = ([b"Host: x"] if host else []) + (headers or [])
    return line + b"\r\n" + b"".join(h + b"\r\n" for h in hs) + b"\r\n" + body


def cases() -> list[tuple[str, bytes, bool]]:
    out = []
    for b in range(256):
        c = bytes([b])
        out.append((f"target-byte {b:#04x}", req(b"GET /items/1" + c + b" HTTP/1.1"), False))
        out.append((f"target-first {b:#04x}", req(b"GET " + c + b"/health HTTP/1.1"), False))
        out.append((f"header-value {b:#04x}", req(headers=[b"X-A: a" + c + b"b"]), False))
        out.append((f"header-name {b:#04x}", req(headers=[b"X" + c + b"A: v"]), False))
        out.append((f"method {b:#04x}", req(b"G" + c + b"T /health HTTP/1.1"), False))
    special = {
        "no-host-1.1": req(host=False),
        "no-host-1.0": req(b"GET /health HTTP/1.0", host=False),
        "http-1.0": req(b"GET /health HTTP/1.0"),
        "http-1.0-keepalive": req(b"GET /health HTTP/1.0", [b"Connection: keep-alive"]),
        "http-2.0": req(b"GET /health HTTP/2.0"),
        "http-lower": req(b"GET /health http/1.1"),
        "http-1.2": req(b"GET /health HTTP/1.2"),
        "two-hosts": req(headers=[b"Host: y"]),
        "conn-close": req(headers=[b"Connection: close"]),
        "conn-Close-list": req(headers=[b"Connection: keep-alive, CLOSE"]),
        "bare-lf": b"GET /health HTTP/1.1\nHost: x\n\n",
        "mixed-lf": b"GET /health HTTP/1.1\r\nHost: x\n\r\n",
        "obs-fold": req(headers=[b"X-A: a", b" b"]),
        "leading-crlf": b"\r\n" + req(),
        "double-space": req(b"GET  /health HTTP/1.1"),
        "trailing-space": req(b"GET /health HTTP/1.1 "),
        "space-before-colon": req(headers=[b"X-A : v"]),
        "empty-header-value": req(headers=[b"X-A:"]),
        "lower-method": req(b"get /health HTTP/1.1"),
        "absolute-target": req(b"GET http://x/health HTTP/1.1"),
        "star-target": req(b"OPTIONS * HTTP/1.1"),
        "cl-te": req(b"POST /items HTTP/1.1", [b"Content-Type: application/json", b"Content-Length: 5",
                                                b"Transfer-Encoding: chunked"], N + b"\r\n" + GOOD + b"\r\n0\r\n\r\n"),
        "chunked": req(b"POST /items HTTP/1.1", [b"Content-Type: application/json", b"Transfer-Encoding: chunked"],
                       b"10\r\n" + GOOD[:16] + b"\r\n%x;ext=1\r\n" % (len(GOOD) - 16) + GOOD[16:]
                       + b"\r\n0\r\nX-T: 1\r\n\r\n"),
        "chunked-upper": req(b"POST /items HTTP/1.1", [b"Content-Type: application/json", b"Transfer-Encoding: CHUNKED"],
                             N + b"\r\n" + GOOD + b"\r\n0\r\n\r\n"),
        "chunk-bad-footer": req(b"POST /items HTTP/1.1", [b"Content-Type: application/json", b"Transfer-Encoding: chunked"],
                                b"%x\r\n" % (len(GOOD) + 1) + GOOD + b"\r\n0\r\n\r\n"),
        "te-gzip": req(b"POST /items HTTP/1.1", [b"Transfer-Encoding: gzip"], b"x"),
        "te-gzip-chunked": req(b"POST /items HTTP/1.1", [b"Transfer-Encoding: gzip, chunked"], b"0\r\n\r\n"),
        "te-twice": req(b"POST /items HTTP/1.1", [b"Transfer-Encoding: chunked", b"Transfer-Encoding: chunked"],
                        b"0\r\n\r\n"),
        "chunk-bad-size": req(b"POST /items HTTP/1.1", [b"Transfer-Encoding: chunked"], b"zz\r\nab\r\n0\r\n\r\n"),
        "chunk-no-crlf": req(b"POST /items HTTP/1.1", [b"Transfer-Encoding: chunked"], b"2\r\nabX0\r\n\r\n"),
        "chunk-big-hex": req(b"POST /items HTTP/1.1", [b"Transfer-Encoding: chunked"], b"0000000000000000000000002\r\nab\r\n0\r\n\r\n"),
        "cl-plus": req(b"POST /items HTTP/1.1", [b"Content-Length: +5"], b"hello"),
        "cl-neg": req(b"POST /items HTTP/1.1", [b"Content-Length: -1"]),
        "cl-two-same": req(b"POST /items HTTP/1.1", [b"Content-Length: 2", b"Content-Length: 2"], b"{}"),
        "cl-two-diff": req(b"POST /items HTTP/1.1", [b"Content-Length: 2", b"Content-Length: 3"], b"{}x"),
        "cl-list": req(b"POST /items HTTP/1.1", [b"Content-Length: 2, 2"], b"{}"),
        "cl-space": req(b"POST /items HTTP/1.1", [b"Content-Length:  2 "], b"{}"),
        "cl-hex": req(b"POST /items HTTP/1.1", [b"Content-Length: 0x2"], b"{}"),
        "cl-leading-zero": req(b"POST /items HTTP/1.1", [b"Content-Type: application/json", b"Content-Length: 0035"], GOOD),
        "get-with-body": req(b"GET /health HTTP/1.1", [b"Content-Length: 4"], b"abcd"),
        "expect-100": req(b"POST /items HTTP/1.1", [b"Content-Type: application/json", b"Expect: 100-continue",
                                                    b"Content-Length: 35"], GOOD),
        "expect-100-get": req(b"GET /health HTTP/1.1", [b"Expect: 100-continue", b"Content-Length: 2"], b"{}"),
        "head-health": req(b"HEAD /health HTTP/1.1"),
        "head-404": req(b"HEAD /nope HTTP/1.1"),
        "pipelined": req() + req(b"GET /stats HTTP/1.1"),
    }
    for size in (8000, 16384, 17000, 70000, 127900, 127920, 127933, 127934, 127950, 200000, 300000):
        special[f"head-size-{size}"] = req(headers=[b"X-A: " + b"a" * size])
        special[f"target-size-{size}"] = req(b"GET /items/" + b"1" * size + b" HTTP/1.1")
    for size in (2**20, 5 * 2**20):
        special[f"body-size-{size}"] = req(b"POST /items HTTP/1.1", [b"Content-Type: application/json",
                                           b"Content-Length: %d" % (size + 2)], b'"' + b"a" * size + b'"')
    out += [(name, data, True) for name, data in special.items()]
    return out


def main() -> int:
    python, rust = start_pair(ROOT / "rust_app" / "target" / "release" / "stockroom")
    bad = 0
    try:
        for name, data, check_close in cases():
            p = exchange(python.port, data, check_close)
            r = exchange(rust.port, data, check_close)
            if p != r:
                bad += 1
                if bad <= 40:
                    print(f"DIFF {name}\n     python={str(p)[:200]}\n     rust  ={str(r)[:200]}")
    finally:
        python.stop()
        rust.stop()
    print(f"{len(cases()) - bad}/{len(cases())} same")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
