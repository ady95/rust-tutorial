"""기준 구현 서버를 띄운다. Rust 구현과 같은 명령행을 쓴다: run_server.py [--host H] [--port P]

uvicorn 작업자 하나(이벤트 루프 하나)로 실행한다. 접근 로그는 끈다.
"""

import argparse
import sys
from pathlib import Path

import uvicorn

sys.path.insert(0, str(Path(__file__).resolve().parent))


def main() -> None:
    parser = argparse.ArgumentParser(prog="stockroom")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    uvicorn.run("stockroom.app:app", host=args.host, port=args.port, workers=1, access_log=False, log_level="warning")


if __name__ == "__main__":
    main()
