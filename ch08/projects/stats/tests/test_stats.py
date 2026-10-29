from pathlib import Path

import pytest

from stats import main

FIXTURES = Path(__file__).parent / "fixtures"


def run(capsys: pytest.CaptureFixture[str], *args: str) -> tuple[int, str, str]:
    code = main([*args])
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def test_integers(capsys: pytest.CaptureFixture[str]) -> None:
    code, out, err = run(capsys, str(FIXTURES / "integers.txt"))
    assert code == 0
    assert err == ""
    assert out == "count: 5\nsum: 15.0\nmean: 3.0\nmean2: 3.0\nstdev: 1.5811\nmin: 1.0\nmax: 5.0\n"


def test_float_rules_python_specific(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    path = tmp_path / "cancel.txt"
    path.write_text("1e16\n1\n-1e16\n", encoding="utf-8")
    _, out, _ = run(capsys, str(path))
    assert "sum: 1.0\n" in out  # 오차 보정 합산 (단순 합산이면 0.0)


@pytest.mark.parametrize("text", ["inf", "-inf", "nan", "1e400", "Infinity"])
def test_non_finite_is_an_error(text: str, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    path = tmp_path / "x.txt"
    path.write_text(f"1\n{text}\n", encoding="utf-8")
    code, out, err = run(capsys, str(path))
    assert code == 1
    assert out == ""
    assert err == f"stats: error: not a finite number on line 2: {text}\n"


def test_bad_line(capsys: pytest.CaptureFixture[str]) -> None:
    code, _, err = run(capsys, str(FIXTURES / "bad_line.txt"))
    assert code == 1
    assert err == "stats: error: not a number on line 3: abc\n"
