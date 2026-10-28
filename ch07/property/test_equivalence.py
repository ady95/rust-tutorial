"""pytest 로 돌리는 Python·Rust 비교 속성 테스트 (07-2).

사용법 (ch07/property 에서): RUST_BIN=<Rust 실행 파일> uv run pytest -q test_equivalence.py
"""

import os

from hypothesis import given, settings
from hypothesis import strategies as st

from equivalence import compare

RUST = os.environ.get("RUST_BIN", "rust_app/target/release/wordfreq")


@settings(max_examples=2000, deadline=None)
@given(text=st.text(max_size=40), top=st.integers(1, 20), as_json=st.booleans())
def test_same_as_python(text: str, top: int, as_json: bool) -> None:
    expected, actual = compare(RUST, text, top, as_json)
    assert expected == actual
