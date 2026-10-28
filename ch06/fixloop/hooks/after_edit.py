"""PostToolUse 훅: .rs 파일을 쓰거나 고치면 cargo fmt 와 cargo check 를 실행한다 (06-3).

cargo check 가 실패하면 짧은 형식(--message-format short)의 오류 줄을 종료 코드 2 와 stderr 로
Claude 에게 돌려준다. 파일은 이미 고쳐진 뒤이므로 막는 것이 아니라 결과를 알려 주는 것이다.
실행할 때마다 reports/hook_log.jsonl 에 오류 수를 남긴다.
"""

import json
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[2]
LOG = PROJECT / "reports" / "hook_log.jsonl"
MAX_LINES = 30


def cargo() -> str:
    return shutil.which("cargo") or str(Path.home() / ".cargo" / "bin" / "cargo")


def main() -> int:
    sys.stderr.reconfigure(encoding="utf-8")
    event = json.load(sys.stdin)
    file_path = Path(event.get("tool_input", {}).get("file_path", ""))
    if file_path.suffix != ".rs":
        return 0
    fmt = subprocess.run([cargo(), "fmt"], cwd=PROJECT, capture_output=True, text=True)
    check = subprocess.run(
        [cargo(), "check", "--all-targets", "--message-format", "short"],
        cwd=PROJECT, capture_output=True, text=True,
    )
    errors = [line for line in check.stderr.splitlines() if ": error" in line]
    LOG.parent.mkdir(exist_ok=True)
    with LOG.open("a", encoding="utf-8") as log:
        entry = {
            "time": datetime.now().isoformat(timespec="seconds"),
            "file": file_path.name,
            "fmt": fmt.returncode,
            "check": check.returncode,
            "errors": len(errors),
        }
        log.write(json.dumps(entry, ensure_ascii=False) + "\n")
    if fmt.returncode != 0:
        print(f"cargo fmt 실패(문법 오류일 수 있음):\n{fmt.stderr[-1500:]}", file=sys.stderr)
        return 2
    if check.returncode != 0:
        shown = errors[:MAX_LINES] or check.stderr.splitlines()[-MAX_LINES:]
        more = f"\n... 외 {len(errors) - MAX_LINES}개" if len(errors) > MAX_LINES else ""
        print(f"cargo check 실패 ({len(errors)}개 오류):\n" + "\n".join(shown) + more, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
