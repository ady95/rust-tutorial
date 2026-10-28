"""Stop 훅: Claude 가 작업을 끝내려 할 때 완료 조건을 검사한다 (05-3).

검사: 기준 고정(baseline) → cargo fmt --check → clippy → cargo test → release 빌드 → compare.py
하나라도 실패하면 종료 코드 2 와 stderr 로 실패 내용을 Claude 에게 돌려줘 작업을 계속하게 한다.
compare.py 의 종료 코드 3(프로그램 실행 불가)은 코드 문제가 아니므로 막지 않고 기록만 한다.
같은 세션에서 연속 3번 막았는데도 실패하면 더 막지 않고 gave_up 으로 기록한다.
검사할 때마다 reports/stop_checks.jsonl 에 결과를 한 줄씩 남긴다.
"""

import json
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[2]
RUST_APP = PROJECT / "rust_app"
BASELINE = PROJECT.parents[1] / "tools" / "baseline.py"
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


def run(cmd: list[str], cwd: Path) -> tuple[int, str]:
    try:
        proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    except OSError as err:
        return -1, str(err)
    return proc.returncode, (proc.stdout + proc.stderr)[-1500:]


def main() -> int:
    # stderr 인코딩을 UTF-8 로 고정한다. 기본값은 Python 버전·설정에 따라 다를 수 있다 (02-1)
    sys.stderr.reconfigure(encoding="utf-8")
    event = json.load(sys.stdin)
    checks: list[tuple[str, list[str], Path]] = [
        ("baseline", [sys.executable, str(BASELINE), "check"], PROJECT),
    ]
    if (RUST_APP / "Cargo.toml").exists():
        checks += [
            ("fmt", [cargo(), "fmt", "--check"], RUST_APP),
            ("clippy", [cargo(), "clippy", "--all-targets", "--", "-D", "warnings"], RUST_APP),
            ("test", [cargo(), "test"], RUST_APP),
            ("build", [cargo(), "build", "--release"], RUST_APP),
            ("compare", [sys.executable, "automation/compare.py"], PROJECT),
        ]
    failures: list[str] = []
    results: dict[str, int] = {}
    for name, cmd, cwd in checks:
        code, output = run(cmd, cwd)
        results[name] = code
        if name == "compare" and code == 3:
            continue  # 실행 환경 문제: 코드를 고쳐도 해결되지 않는다
        if name == "test" and code != 0 and "4551" in output:
            results[name] = 3  # 테스트 실행 파일이 운영체제 정책에 막힘(02-2). 코드 문제가 아니다
            continue
        if code != 0:
            failures.append(f"[{name}] 종료 코드 {code}\n{output}")
            if name == "build":
                break  # 빌드가 안 되면 비교는 의미 없다
    if not (RUST_APP / "Cargo.toml").exists():
        failures.append("[rust_app] Cargo.toml 이 없습니다. Rust 프로젝트가 아직 없습니다")

    session = event.get("session_id")
    # 연속으로 막을 수 있는 횟수에 상한을 둔다. 상한이 없으면 고칠 수 없는 실패에서 끝없이 돈다
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
