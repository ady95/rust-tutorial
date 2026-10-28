"""승인한 기준 구현을 고정하고, 바뀌지 않았는지 검사한다 (03-4).

사용법 (실습 프로젝트 폴더에서):
    uv run --no-project python ../../tools/baseline.py lock    # 사람이 승인할 때 1회
    uv run --no-project python ../../tools/baseline.py check   # 에이전트 작업 전후

lock 은 보호 대상 파일의 SHA-256 을 baseline.lock 에 적는다.
check 는 지금 파일과 baseline.lock 을 비교한다.

종료 코드: 0 = 그대로, 1 = 바뀐 파일 있음, 2 = baseline.lock 없음.
"""

from __future__ import annotations

import hashlib
import sys
from datetime import date
from pathlib import Path

# 사람이 소유하는 것들. 에이전트는 rust_app/ 과 reports/ 만 쓴다
PROTECTED = ["python_src", "tests", "contracts", "automation", ".python-version", "pyproject.toml", "uv.lock"]
LOCK_NAME = "baseline.lock"
SKIP_DIRS = {"__pycache__", ".pytest_cache", ".hypothesis"}


def protected_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for name in PROTECTED:
        path = root / name
        if path.is_file():
            files.append(path)
        elif path.is_dir():
            files.extend(
                p for p in path.rglob("*") if p.is_file() and not SKIP_DIRS.intersection(p.relative_to(root).parts)
            )
    return sorted(files)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def snapshot(root: Path) -> dict[str, str]:
    return {p.relative_to(root).as_posix(): digest(p) for p in protected_files(root)}


def read_lock(lock: Path) -> dict[str, str]:
    entries: dict[str, str] = {}
    for line in lock.read_text(encoding="utf-8").splitlines():
        if line and not line.startswith("#"):
            sha, rel = line.split("  ", 1)
            entries[rel] = sha
    return entries


def lock(root: Path) -> int:
    current = snapshot(root)
    lines = [f"# approved {date.today().isoformat()} — 이 파일은 사람이 승인할 때만 다시 만든다"]
    lines += [f"{sha}  {rel}" for rel, sha in current.items()]
    (root / LOCK_NAME).write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"locked {len(current)} files -> {LOCK_NAME}")
    return 0


def check(root: Path) -> int:
    lock_path = root / LOCK_NAME
    if not lock_path.exists():
        print(f"baseline: {LOCK_NAME} not found. 기준 구현이 아직 승인되지 않았습니다", file=sys.stderr)
        return 2
    locked, current = read_lock(lock_path), snapshot(root)
    problems = [f"changed: {rel}" for rel in locked if rel in current and current[rel] != locked[rel]]
    problems += [f"removed: {rel}" for rel in locked if rel not in current]
    problems += [f"added:   {rel}" for rel in current if rel not in locked]
    for problem in problems:
        print(f"baseline: {problem}", file=sys.stderr)
    if problems:
        return 1
    print(f"baseline OK ({len(locked)} files)")
    return 0


def main(argv: list[str]) -> int:
    if len(argv) != 1 or argv[0] not in ("lock", "check"):
        print("usage: baseline.py lock|check", file=sys.stderr)
        return 2
    root = Path.cwd()
    return lock(root) if argv[0] == "lock" else check(root)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
