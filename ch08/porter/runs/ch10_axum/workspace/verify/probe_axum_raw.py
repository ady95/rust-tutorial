"""axum 전환 후 원시 HTTP 요청의 응답을 출력한다(헤더 검사 실패·Date 헤더 등 비교 도구가 다루지 않는 부분)."""
import socket
import subprocess
import time

PORT = 18431
proc = subprocess.Popen(["rust_app/target/release/stockroom", "--port", str(PORT)])
time.sleep(0.7)


def raw(data: bytes) -> bytes:
    s = socket.create_connection(("127.0.0.1", PORT))
    s.sendall(data)
    s.settimeout(1)
    out = b""
    try:
        while chunk := s.recv(4096):
            out += chunk
    except OSError:
        pass
    return out


try:
    print(raw(b"GET /health HTTP/1.1\r\nHost: x\r\nConnection: close\r\n\r\n"))
    print(raw(b"GET /health HTTP/1.1\r\n\r\n"))
    print(raw(b"BAD\r\n\r\n"))
finally:
    proc.kill()
