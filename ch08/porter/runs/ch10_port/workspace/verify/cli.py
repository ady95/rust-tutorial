"""명령행 인자 처리를 기준(run_server.py, argparse)과 Rust 바이너리에서 비교한다.

비교: 종료 코드, stdout, stderr. 서버가 뜨는 인자는 1.5초 안에 끝나지 않으면 "running" 으로 본다.
사용법: uv run python verify/cli.py
"""

import socket
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RUST = str(ROOT / "rust_app" / "target" / "release" / "stockroom")
PY = [sys.executable, str(ROOT / "python_src" / "run_server.py")]


def free_port() -> str:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return str(sock.getsockname()[1])


def run(cmd: list[str]) -> tuple:
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        out, err = proc.communicate(timeout=1.5)
        return proc.returncode, out, err
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.communicate()
        return ("running",)


def main() -> int:
    p = free_port()
    cases = [["-h"], ["--help"], ["--he"], ["--h"], ["--port"], ["--port", "x"], ["--port=x"], ["--port", ""],
             ["--bogus"], ["extra"], ["-x"], ["--port", "1", "--port"], ["--host"], ["--port", "99999"],
             ["--port", " 1_0 "], ["--port", "-1"], ["--", "x"], ["-"], ["--port", p], [f"--port={p}"], ["--po", p],
             ["--p", p], ["--host", "127.0.0.1", "--port", p], ["--hos=127.0.0.1", "--port", p], ["--port", "+" + p],
             ["--port", " " + p], ["--port", p + "\n"], ["--port", "٣"], ["-h", "--bogus"], ["--port=", p]]
    bad = 0
    for args in cases:
        a, b = run(PY + args), run([RUST, *args])
        if a != b:
            bad += 1
            print(f"DIFF {args}\n     python={a!r:.300}\n     rust  ={b!r:.300}")
    print(f"{len(cases) - bad}/{len(cases)} same")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
