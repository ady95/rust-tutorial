"""두 서버(기준 구현, Rust 구현)를 띄우고 같은 요청을 보내 계약 4절의 규칙으로 응답을 비교하는 공용 도구.

compare.py(정해 둔 케이스)와 fuzz.py(무작위 요청열)가 쓴다.
요청은 http.client 로 직접 만들어 본문 바이트와 헤더를 그대로 보낸다.
"""

from __future__ import annotations

import base64
import http.client
import json
import os
import socket
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
COMPARED_HEADERS = ("content-type", "location", "allow")


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@dataclass
class Server:
    name: str
    port: int
    proc: subprocess.Popen
    conn: http.client.HTTPConnection | None = None

    def request(self, method: str, path: str, body: bytes | None, headers: dict[str, str]) -> tuple[int, dict, bytes]:
        for attempt in range(2):  # 서버가 연결을 닫았으면 한 번 다시 연결
            try:
                if self.conn is None:
                    self.conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
                self.conn.request(method, path, body=body, headers=headers)
                response = self.conn.getresponse()
                data = response.read()
                found = {k.lower(): v for k, v in response.getheaders()}
                if found.get("connection", "").lower() == "close":
                    self.conn.close()
                    self.conn = None
                return response.status, found, data
            except (ConnectionError, http.client.HTTPException, OSError):
                if self.conn is not None:
                    self.conn.close()
                self.conn = None
                if attempt == 1:
                    raise
        raise RuntimeError("unreachable")

    def stop(self) -> None:
        if self.conn is not None:
            self.conn.close()
        self.proc.terminate()
        try:
            self.proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.proc.kill()


def start(name: str, cmd: list[str]) -> Server:
    port = free_port()
    env = dict(os.environ, STOCKROOM_TEST="1")
    proc = subprocess.Popen([*cmd, "--port", str(port)], cwd=ROOT, env=env,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    server = Server(name, port, proc)
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            raise RuntimeError(f"{name} server exited with code {proc.returncode}")
        try:
            if server.request("GET", "/health", None, {})[0] == 200:
                return server
        except OSError:
            time.sleep(0.05)
    server.stop()
    raise RuntimeError(f"{name} server did not answer /health")


def start_pair(rust_binary: Path) -> tuple[Server, Server]:
    python = start("python", [sys.executable, "python_src/run_server.py"])
    try:
        rust = start("rust", [str(rust_binary.resolve())])
    except Exception:
        python.stop()
        raise
    return python, rust


def encode(step: dict) -> tuple[bytes | None, dict[str, str]]:
    headers = dict(step.get("headers", {}))
    if "json" in step:
        headers.setdefault("Content-Type", "application/json")
        return json.dumps(step["json"], ensure_ascii=False, separators=(",", ":")).encode(), headers
    if "body" in step:
        return step["body"].encode("utf-8"), headers
    if "body_b64" in step:
        return base64.b64decode(step["body_b64"]), headers
    return None, headers


def normalize(server: Server, status: int, headers: dict, body: bytes) -> dict:
    out = {"status": status}
    for name in COMPARED_HEADERS:
        if name in headers:
            out[name] = headers[name].replace(f"127.0.0.1:{server.port}", "<host>")
    if status == 422:
        try:
            out["errors"] = [[e["type"], e["loc"]] for e in json.loads(body)["detail"]]
        except (ValueError, KeyError, TypeError):
            out["body"] = body  # 계약 형식이 아니면 바이트 그대로 비교(다르게 나온다)
    else:
        out["body"] = body
    return out


def run_steps(python: Server, rust: Server, steps: list[dict]) -> list[str]:
    """상태를 비운 뒤 요청을 차례로 보내고, 처음 다른 응답에서 멈춘다. 차이가 없으면 빈 목록."""
    for server in (python, rust):
        if server.request("POST", "/_test/reset", None, {})[0] != 204:
            return [f"{server.name}: /_test/reset failed"]
    for index, step in enumerate(steps, 1):
        body, headers = encode(step)
        got = [normalize(s, *s.request(step["method"], step["path"], body, headers)) for s in (python, rust)]
        if got[0] != got[1]:
            label = f"step {index}: {step['method']} {step['path']}"
            diffs = [f"{key}: python={got[0].get(key)!r:.200} rust={got[1].get(key)!r:.200}"
                     for key in sorted(set(got[0]) | set(got[1])) if got[0].get(key) != got[1].get(key)]
            return [label, *diffs]
    return []
