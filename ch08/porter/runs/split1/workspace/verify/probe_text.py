"""rust_app 단위 테스트의 기대값을 기준 구현(Python 3.12)으로 계산해 출력한다 (위험 R1, R2, R5, R8, R10, R11).

출력의 문자열은 Rust 문자열 리터럴 형식(비ASCII·제어 문자는 \\u{..})으로 쓴다.
사용법 (프로젝트 루트에서): python3 verify/probe_text.py
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("wordfreq_ref", ROOT / "python_src" / "wordfreq.py")
ref = importlib.util.module_from_spec(_spec)
sys.modules["wordfreq_ref"] = ref
_spec.loader.exec_module(ref)


def rs(s: str) -> str:
    out = []
    for c in s:
        if c == '"':
            out.append('\\"')
        elif c == "\\":
            out.append("\\\\")
        elif 0x20 <= ord(c) < 0x7F:
            out.append(c)
        else:
            out.append("\\u{%x}" % ord(c))
    return '"' + "".join(out) + '"'


TOKENIZE = [
    "a\x1cb a\x1fb",
    "a\x0bb",
    "a　b",
    "a\x85b",
    "a​b",
    "a᠎b",
    "a﻿b",
    "a b c\xa0d e",
    "﻿hello hello",
    "a\rb",
    "a\x00b",
    '"Hello," Don\'t e-mail... RUST!',
    "é e z � \U0001f600 z",
]

LOWER = [
    "İ",
    "ΑΣ",
    "Σ",
    "ΑΣΑ",
    "ΑΣ'Β",
    "ΆΣ",
    "ΑΣ́",
    "ΑΣΣ",
    "'Σ",
    # Rust 17.0 과 분류가 다른 글자가 문맥에 있는 경우
    "ʕΣ",
    "Α\U0001171eΣ",
    "ΑΣᲉ",
    "ΑΣ\U00010d50",
    "ΑࢗΣ",
    # Rust 17.0 에서만 대소문자 쌍이 있는 글자
    "ᲉꟋꟌꟜ\U00010d50\U00016ea0",
]

JSON = ["a\x00b", "a\x08b", "a\x7fb", 'a"b', "a\\b", "a‎b", "a\x1bb a\x0cb", "", "러스트 러스트 rust"]

PATHS = ["", ".", "tests/fixtures/basic.txt/", "tests/fixtures/basic.txt/.", "tests/fixtures/./basic.txt",
         "a//b", "a/../b", "./a", "//a", "///a"]


def main() -> int:
    print("== tokenize")
    for text in TOKENIZE:
        print(f"{rs(text)} => [{', '.join(rs(w) for w in ref.tokenize(text))}]")
    print("== count_words order (top=maxsize)")
    rep = ref.count_words(ref.tokenize("é e z � \U0001f600 z"), sys.maxsize)
    print(rep)
    print("== lower")
    for text in LOWER:
        print(f"{rs(text)} => {rs(text.lower())}")
    print("== tokenize keeps sigma context after strip: 'ΑΣ.' 'ΑΣ.Β' '(ΑΣ)'")
    for text in ["ΑΣ.", "ΑΣ.Β", "(ΑΣ)", "ΑΣ'"]:
        print(f"{rs(text)} => [{', '.join(rs(w) for w in ref.tokenize(text))}]")
    print("== json")
    for text in JSON:
        print(f"{rs(text)} => {rs(ref.format_json(ref.count_words(ref.tokenize(text), 10)))}")
    print("== text")
    for text in ["b a b", ""]:
        print(f"{rs(text)} => {rs(ref.format_text(ref.count_words(ref.tokenize(text), 10)))}")
    print("== pathlib")
    for p in PATHS:
        print(f"{rs(p)} => {rs(str(Path(p)))} (posix {rs(str(PurePosixPath(p)))})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
