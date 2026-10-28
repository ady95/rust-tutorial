"""Python 기준 구현(ch05/wordfreq/python_src/wordfreq.py)과 Rust 실행 파일의 출력을 비교하는 도구 (07-2).

expected(): 기준 구현의 함수를 같은 프로세스에서 불러 기대 출력을 만든다(파일 읽기 방식까지 같게)
actual()  : Rust 실행 파일을 같은 파일로 실행한다
STRATEGIES: 입력 생성 전략 세 가지
"""

import importlib.util
import string
import subprocess
import sys
import tempfile
from pathlib import Path

from hypothesis import strategies as st

ROOT = Path(__file__).resolve().parents[2]
REFERENCE = ROOT / "ch05" / "wordfreq" / "python_src" / "wordfreq.py"

_spec = importlib.util.spec_from_file_location("wordfreq_ref", REFERENCE)
ref = importlib.util.module_from_spec(_spec)
sys.modules["wordfreq_ref"] = ref  # dataclass 가 모듈을 찾을 수 있도록 실행 전에 등록
_spec.loader.exec_module(ref)


def expected(path: Path, top: int, as_json: bool) -> tuple[bytes, int]:
    text = path.read_text(encoding="utf-8")  # 기준 구현과 같은 읽기(줄바꿈 변환 포함)
    report = ref.count_words(ref.tokenize(text), top)
    out = ref.format_json(report) if as_json else ref.format_text(report)
    return out.encode("utf-8"), 0


def actual(binary: Path, path: Path, top: int, as_json: bool) -> tuple[bytes, int]:
    cmd = [str(binary), str(path), "--top", str(top)] + (["--json"] if as_json else [])
    proc = subprocess.run(cmd, capture_output=True, timeout=30)
    return proc.stdout, proc.returncode


def compare(binary: Path, text: str, top: int, as_json: bool) -> tuple[tuple[bytes, int], tuple[bytes, int]]:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "input.txt"
        path.write_text(text, encoding="utf-8", newline="")
        return expected(path, top, as_json), actual(binary, path, top, as_json)


# 1) 아무 Unicode 문자열 (Hypothesis 기본, 서로게이트 제외)
any_text = st.text(max_size=40)

# 2) 위험한 문맥: 글자 + Σ(대문자 시그마). 어말 시그마 규칙은 앞 글자의 대소문자 성질에 달려 있다
letter = st.characters(categories=("Lu", "Ll", "Lt", "Lm", "Lo"))
sigma_words = st.lists(
    st.tuples(st.text(letter, min_size=1, max_size=2), st.sampled_from(["Σ", "Σa", "ΣΣ"])).map("".join),
    min_size=1, max_size=8,
).map(" ".join)

# 3) 기준 런타임이 모르는 글자: Python 3.12 의 Unicode 15.0 에서 미할당(Cn)인 코드 포인트.
#    Rust 표준 라이브러리는 더 새로운 Unicode 를 쓰므로 이 글자들의 대소문자 정보가 다를 수 있다
unassigned = st.characters(categories=("Cn",))
unassigned_words = st.lists(
    st.tuples(st.sampled_from(["", "A", "Σ"]), st.text(unassigned, min_size=1, max_size=2), st.sampled_from(["", "B", "Σ"])).map("".join),
    min_size=1, max_size=8,
).map(" ".join)

STRATEGIES = {"any_text": any_text, "sigma_words": sigma_words, "unassigned_words": unassigned_words}
ASCII = string.ascii_letters
