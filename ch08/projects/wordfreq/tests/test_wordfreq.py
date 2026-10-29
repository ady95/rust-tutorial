import os
import sys
from pathlib import Path

import pytest

from wordfreq import count_words, main, tokenize

FIXTURES = Path(__file__).parent / "fixtures"


def run(capsys: pytest.CaptureFixture[str], *args: str) -> tuple[int, str, str]:
    code = main([*args])
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def test_tokenize_strips_punctuation_and_lowercases() -> None:
    assert tokenize('"Hello," Don\'t e-mail... RUST!') == ["hello", "don't", "e-mail", "rust"]


def test_tokenize_drops_punctuation_only_pieces() -> None:
    assert tokenize("!!! --- ...") == []


def test_ties_are_sorted_by_word() -> None:
    report = count_words(["b", "a", "c", "b", "a", "c", "d"], top_n=10)
    assert report.top == [("a", 2), ("b", 2), ("c", 2), ("d", 1)]


def test_basic_text_output(capsys: pytest.CaptureFixture[str]) -> None:
    code, out, err = run(capsys, str(FIXTURES / "basic.txt"))
    assert code == 0
    assert err == ""
    assert out == "words: 10\nunique: 6\n3\trust\n2\tis\n2\tpython\n1\tand\n1\tfast\n1\tfriendly\n"


def test_top_limits_lines(capsys: pytest.CaptureFixture[str]) -> None:
    code, out, _ = run(capsys, str(FIXTURES / "basic.txt"), "--top", "2")
    assert code == 0
    assert out == "words: 10\nunique: 6\n3\trust\n2\tis\n"


def test_korean_json_output(capsys: pytest.CaptureFixture[str]) -> None:
    code, out, _ = run(capsys, str(FIXTURES / "korean.txt"), "--json", "--top", "3")
    assert code == 0
    assert out == (
        '{"words":12,"unique":11,"top":['
        '{"word":"러스트는","count":2},{"word":"python","count":1},{"word":"rust와","count":1}]}\n'
    )


def test_empty_file(capsys: pytest.CaptureFixture[str]) -> None:
    code, out, _ = run(capsys, str(FIXTURES / "empty.txt"), "--json")
    assert code == 0
    assert out == '{"words":0,"unique":0,"top":[]}\n'


def test_missing_file(capsys: pytest.CaptureFixture[str]) -> None:
    code, out, err = run(capsys, "no_such_file.txt")
    assert code == 1
    assert out == ""
    assert err == "wordfreq: error: file not found: no_such_file.txt\n"


def test_invalid_utf8(capsys: pytest.CaptureFixture[str]) -> None:
    path = str(FIXTURES / "invalid_utf8.txt")
    code, out, err = run(capsys, path)
    assert code == 1
    assert out == ""
    assert err == f"wordfreq: error: not valid UTF-8: {path}\n"


def test_directory_is_not_readable(capsys: pytest.CaptureFixture[str]) -> None:
    code, _, err = run(capsys, str(FIXTURES))
    assert code == 1
    assert err == f"wordfreq: error: cannot read file: {FIXTURES}\n"


@pytest.mark.parametrize("args", [[], ["x.txt", "--top", "0"], ["x.txt", "--top", "abc"], ["x.txt", "--bogus"]])
def test_usage_errors_exit_2(args: list[str], capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        main(args)
    assert exc.value.code == 2
    assert capsys.readouterr().err != ""


# --- 2판(08장)에서 추가한 규칙 ---


@pytest.mark.parametrize("value", ["２", "1_0", "+3", " 3", "3 ", "-1", "", "0", "000"])
def test_top_accepts_ascii_digits_only(value: str, capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        main([str(FIXTURES / "basic.txt"), "--top", value])
    assert exc.value.code == 2
    assert capsys.readouterr().err != ""


def test_top_leading_zero_and_huge(capsys: pytest.CaptureFixture[str]) -> None:
    _, two, _ = run(capsys, str(FIXTURES / "basic.txt"), "--top", "2")
    _, leading, _ = run(capsys, str(FIXTURES / "basic.txt"), "--top", "002")
    _, all_words, _ = run(capsys, str(FIXTURES / "basic.txt"), "--top", "100")
    _, huge, _ = run(capsys, str(FIXTURES / "basic.txt"), "--top", "9" * 5000)
    assert leading == two
    assert huge == all_words


@pytest.mark.skipif(sys.platform == "win32", reason="UTF-8 이 아닌 파일 이름은 POSIX 에서만 만들 수 있다")
def test_non_utf8_missing_file_name_is_replaced(capsys: pytest.CaptureFixture[str]) -> None:
    name = os.fsdecode(b"gone\xff.txt")
    code, out, err = run(capsys, name)
    assert code == 1
    assert out == ""
    assert err == "wordfreq: error: file not found: gone�.txt\n"


# --- 3판(11장 이후 결정 반영) ---


def test_option_abbreviation_is_a_usage_error(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        main([str(FIXTURES / "basic.txt"), "--to", "2"])
    assert exc.value.code == 2


@pytest.mark.skipif(sys.platform == "win32", reason="UTF-8 이 아닌 인자는 POSIX 에서만 만들 수 있다")
def test_non_utf8_top_value_is_a_usage_error_not_a_crash(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        main([str(FIXTURES / "basic.txt"), "--top", os.fsdecode(b"\xff")])
    assert exc.value.code == 2
    assert capsys.readouterr().err != ""


def test_trailing_slash_path_reads_the_file(capsys: pytest.CaptureFixture[str]) -> None:
    code, out, _ = run(capsys, str(FIXTURES / "basic.txt") + "/")
    assert code == 0
    assert out.startswith("words: 10\n")
