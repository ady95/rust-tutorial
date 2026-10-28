"""PostToolUse 훅: rust_app 안의 .rs 파일을 쓰거나 고치면 cargo fmt 를 실행한다 (05-3).

입력: 표준 입력으로 받는 훅 JSON (tool_input.file_path).
rustfmt 가 실패하면(문법 오류 등) 종료 코드 2 와 stderr 로 Claude 에게 알린다.
"""

import json
import shutil
import subprocess
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[2]
RUST_APP = PROJECT / "rust_app"


def cargo() -> str:
    return shutil.which("cargo") or str(Path.home() / ".cargo" / "bin" / "cargo")


def main() -> int:
    # stderr 인코딩을 UTF-8 로 고정한다. 기본값은 Python 버전·설정에 따라 다를 수 있다 (02-1)
    sys.stderr.reconfigure(encoding="utf-8")
    event = json.load(sys.stdin)
    file_path = Path(event.get("tool_input", {}).get("file_path", ""))
    if file_path.suffix != ".rs" or RUST_APP not in file_path.resolve().parents:
        return 0
    if not (RUST_APP / "Cargo.toml").exists():
        return 0
    proc = subprocess.run([cargo(), "fmt"], cwd=RUST_APP, capture_output=True, text=True, encoding="utf-8")
    if proc.returncode != 0:
        print(f"cargo fmt 실패:\n{proc.stderr[-2000:]}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
