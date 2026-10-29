"""무작위 입력으로 기준 구현과 Rust 구현을 비교한다 (Hypothesis, 07-2의 any_text 전략).

입력 텍스트·--top·--json 을 Hypothesis 가 만들고, 기준 구현의 함수로 기대 출력을, Rust 실행 파일로 실제 출력을 만든다.
실패하면 Hypothesis 가 줄인 가장 작은 입력을 코드 포인트와 함께 보여 준다.
seed 를 주지 않으면 실행할 때마다 다른 입력을 만든다(반복 실행할수록 더 넓게 시험).

사용법 (프로젝트 루트에서): uv run python automation/fuzz.py [--rust BIN] [--examples 2000] [--seed N]
종료 코드: 0 = 차이 없음, 1 = 차이 발견, 2 = Rust 실행 파일 없음
"""

from __future__ import annotations

import argparse
import importlib.util
import subprocess
import sys
import tempfile
from pathlib import Path

from hypothesis import given, seed, settings
from hypothesis import strategies as st

ROOT = Path(__file__).resolve().parent.parent
REFERENCE = ROOT / "python_src" / "wordfreq.py"

_spec = importlib.util.spec_from_file_location("wordfreq_ref", REFERENCE)
ref = importlib.util.module_from_spec(_spec)
sys.modules["wordfreq_ref"] = ref  # dataclass 가 모듈을 찾을 수 있도록 실행 전에 등록
_spec.loader.exec_module(ref)


def expected(path: Path, top: int, as_json: bool) -> tuple[int, bytes]:
    text = path.read_text(encoding="utf-8")  # 기준 구현과 같은 읽기(줄바꿈 변환 포함)
    report = ref.count_words(ref.tokenize(text), top)
    out = ref.format_json(report) if as_json else ref.format_text(report)
    return 0, out.encode("utf-8")


def actual(binary: Path, path: Path, top: int, as_json: bool) -> tuple[int, bytes]:
    cmd = [str(binary), str(path), "--top", str(top)] + (["--json"] if as_json else [])
    proc = subprocess.run(cmd, capture_output=True, timeout=30)
    return proc.returncode, proc.stdout


def describe(text: str) -> str:
    return " ".join(f"U+{ord(c):04X}" for c in text)


def main() -> int:
    parser = argparse.ArgumentParser(description="Random differential test against the reference.")
    parser.add_argument("--rust", type=Path, default=ROOT / "rust_app" / "target" / "release" / "wordfreq")
    parser.add_argument("--examples", type=int, default=2000)
    parser.add_argument("--seed", type=int)
    args = parser.parse_args()
    if not args.rust.exists():
        print(f"Rust binary not found: {args.rust}", file=sys.stderr)
        return 2
    binary = args.rust.resolve()
    tmp = Path(tempfile.mkdtemp())
    failure: dict[str, object] = {}

    @settings(max_examples=args.examples, deadline=None, database=None)
    @given(text=st.text(max_size=40), top=st.integers(1, 20), as_json=st.booleans())
    def check(text: str, top: int, as_json: bool) -> None:
        path = tmp / "input.txt"
        path.write_text(text, encoding="utf-8", newline="")
        exp, act = expected(path, top, as_json), actual(binary, path, top, as_json)
        if exp != act:
            failure.update(text=text, top=top, as_json=as_json, python=exp, rust=act)
        assert exp == act

    if args.seed is not None:
        check = seed(args.seed)(check)
    try:
        check()
    except AssertionError:
        # Hypothesis 는 줄인 뒤의 마지막 실패 입력으로 한 번 더 실행하므로 failure 에는 최소 입력이 남는다
        print("FAIL random input differs")
        print(f"     text={failure['text']!r} ({describe(str(failure['text']))})")
        print(f"     args: --top {failure['top']}{' --json' if failure['as_json'] else ''}")
        print(f"     python: exit={failure['python'][0]} stdout={failure['python'][1][:200]!r}")
        print(f"     rust:   exit={failure['rust'][0]} stdout={failure['rust'][1][:200]!r}")
        return 1
    print(f"OK   {args.examples} random inputs match")
    return 0


if __name__ == "__main__":
    sys.exit(main())
