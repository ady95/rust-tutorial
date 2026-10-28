import pytest

from main import greet


def test_greet() -> None:
    assert greet("Rust") == "Hello, Rust!"


def test_greet_strips_spaces() -> None:
    assert greet("  Python ") == "Hello, Python!"


def test_greet_empty_name() -> None:
    with pytest.raises(ValueError):
        greet("   ")
