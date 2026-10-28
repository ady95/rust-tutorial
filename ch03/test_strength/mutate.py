"""기준 구현에 작은 결함(변이)을 하나씩 넣고, 테스트가 잡아내는지 본다 (03-3).

ch04/wordfreq 를 임시 폴더에 복사해 변이를 넣은 뒤 두 가지로 검사한다.
- pytest: tests/test_wordfreq.py (함수 호출 + capsys 로 문자열 비교)
- bytes: cases.json 의 케이스를 원본과 변이본으로 각각 실행해 stdout·stderr·종료 코드를 바이트로 비교

사용법 (pytest 가 설치된 ch04/wordfreq 환경을 쓴다):
    cd ch04/wordfreq
    uv run python ../../ch03/test_strength/mutate.py
"""

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[2] / "ch04" / "wordfreq"
TARGET = "python_src/wordfreq.py"

# (이름, 바꿀 코드, 바뀐 코드)
MUTATIONS = [
    ("동률 정렬 기준 삭제", "key=lambda item: (-item[1], item[0])", "key=lambda item: -item[1]"),
    ("앞쪽 문장 부호 남김", "raw.strip(PUNCTUATION)", "raw.rstrip(PUNCTUATION)"),
    ("소문자 변환 삭제", "raw.strip(PUNCTUATION).lower()", "raw.strip(PUNCTUATION)"),
    ("--top 0 허용", "if number < 1:", "if number < 0:"),
    ("JSON 한글 이스케이프", "ensure_ascii=False", "ensure_ascii=True"),
    ("stdout 줄바꿈 고정 삭제", 'sys.stdout.reconfigure(encoding="utf-8", newline="\\n")', 'sys.stdout.reconfigure(encoding="utf-8")'),
]


def copy_project(dest: Path) -> None:
    for name in ("python_src", "tests", "pyproject.toml"):
        src = SOURCE / name
        if src.is_dir():
            shutil.copytree(src, dest / name, ignore=shutil.ignore_patterns("__pycache__"))
        else:
            shutil.copy2(src, dest / name)


def pytest_passes(project: Path) -> bool:
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"], cwd=project, capture_output=True
    )
    return proc.returncode == 0


def run_case(project: Path, args: list[str]) -> tuple[int, bytes, bytes]:
    proc = subprocess.run([sys.executable, "python_src/wordfreq.py", *args], cwd=project, capture_output=True)
    return proc.returncode, proc.stdout, proc.stderr


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    cases = json.loads((SOURCE / "tests" / "cases.json").read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory() as tmp:
        original = Path(tmp) / "original"
        copy_project(original)
        expected = {c["name"]: run_case(original, c["args"]) for c in cases if not c.get("usage_error")}
        expected_codes = {c["name"]: run_case(original, c["args"])[0] for c in cases if c.get("usage_error")}

        print(f"{'변이':<24} pytest  bytes")
        for i, (name, before, after) in enumerate(MUTATIONS):
            project = Path(tmp) / f"m{i}"
            copy_project(project)
            target = project / TARGET
            code = target.read_text(encoding="utf-8")
            assert before in code, f"패턴 없음: {before}"
            target.write_text(code.replace(before, after, 1), encoding="utf-8")

            by_pytest = not pytest_passes(project)
            by_bytes = any(run_case(project, c["args"]) != expected[c["name"]] for c in cases if not c.get("usage_error"))
            by_bytes |= any(run_case(project, c["args"])[0] != expected_codes[c["name"]] for c in cases if c.get("usage_error"))
            print(f"{name:<24} {'잡음' if by_pytest else '놓침':<6}  {'잡음' if by_bytes else '놓침'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
