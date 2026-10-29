import pytest

import hello_ext


def test_add() -> None:
    assert hello_ext.add(2, 3) == 5


def test_argument_types_are_checked() -> None:
    with pytest.raises(TypeError):
        hello_ext.add("2", 3)  # Python 처럼 문자열을 숫자로 바꿔 주지 않는다
    with pytest.raises(OverflowError):
        hello_ext.add(2**63, 0)  # i64 범위를 넘으면 예외


def test_sum_and_percentile() -> None:
    assert hello_ext.sum_floats([0.5, 1.5, 2]) == 4.0
    values = [5.0, 1.0, 4.0, 2.0, 3.0]
    assert [hello_ext.percentile(values, p) for p in (50, 95, 99)] == [3.0, 5.0, 5.0]
    assert values == [5.0, 1.0, 4.0, 2.0, 3.0]  # Vec 으로 복사했으므로 원래 리스트는 그대로


def test_rust_errors_become_python_exceptions() -> None:
    with pytest.raises(ValueError, match="empty list"):
        hello_ext.percentile([], 50)
    with pytest.raises(ValueError, match="NaN"):
        hello_ext.percentile([1.0, float("nan")], 50)


def test_count_words() -> None:
    text = "the quick  brown\tfox\n"
    assert hello_ext.count_words(text) == hello_ext.count_words_holding_gil(text) == len(text.split()) == 4
