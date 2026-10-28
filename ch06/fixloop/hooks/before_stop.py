"""Stop 훅: 작업을 끝내려 할 때 fmt·clippy·test 를 검사한다 (06-3, 06-4).

하나라도 실패하면 종료 코드 2 와 stderr 로 실패 내용을 돌려줘 작업을 계속하게 한다.
같은 세션에서 연속 3번 막았는데도 실패하면 더 막지 않고 gave_up 으로 기록한다 (05-3).
검사할 때마다 reports/stop_checks.jsonl 에 결과를 한 줄씩 남긴다.
"""

import json
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[2]
LOG = PROJECT / "reports" / "stop_checks.jsonl"
MAX_CONSECUTIVE_BLOCKS = 3


def cargo() -> str:
    return shutil.which("cargo") or str(Path.home() / ".cargo" / "bin" / "cargo")


def recent_blocks(session: str | None) -> int:
    """이 세션에서 마지막으로 통과시킨 뒤 연속으로 막은 횟수."""
    if not LOG.exists():
        return 0
    count = 0
    for line in LOG.read_text(encoding="utf-8").splitlines():
        entry = json.loads(line)
        if entry.get("session_id") != session:
            continue
        count = count + 1 if entry.get("blocked") else 0
    return count


def main() -> int:
    sys.stderr.reconfigure(encoding="utf-8")
    event = json.load(sys.stdin)
    checks = [
        ("fmt", [cargo(), "fmt", "--check"]),
        ("clippy", [cargo(), "clippy", "--all-targets", "--", "-D", "warnings"]),
        # --no-fail-fast: 실패한 테스트 파일 하나에서 멈추지 않고 모든 테스트를 실행한다.
        # runF 에서는 이 옵션이 없어 tests/spec.rs 가 훅 안에서 실행되지 않았다 (06-3)
        ("test", [cargo(), "test", "--no-fail-fast"]),
    ]
    failures: list[str] = []
    results: dict[str, int] = {}
    for name, cmd in checks:
        proc = subprocess.run(cmd, cwd=PROJECT, capture_output=True, text=True)
        results[name] = proc.returncode
        if proc.returncode != 0:
            failures.append(f"[{name}] 종료 코드 {proc.returncode}\n{(proc.stdout + proc.stderr)[-1500:]}")

    session = event.get("session_id")
    give_up = bool(failures) and recent_blocks(session) >= MAX_CONSECUTIVE_BLOCKS
    LOG.parent.mkdir(exist_ok=True)
    with LOG.open("a", encoding="utf-8") as log:
        entry = {
            "time": datetime.now().isoformat(timespec="seconds"),
            "session_id": session,
            "stop_hook_active": event.get("stop_hook_active"),
            "results": results,
            "blocked": bool(failures) and not give_up,
            "gave_up": give_up,
        }
        log.write(json.dumps(entry, ensure_ascii=False) + "\n")

    if failures and not give_up:
        print("완료 조건을 통과하지 못했습니다. 고친 뒤 다시 끝내세요.\n\n" + "\n\n".join(failures), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
