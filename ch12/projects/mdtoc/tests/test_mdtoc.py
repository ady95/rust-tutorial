import json
import subprocess
import sys
from pathlib import Path

import pytest

from mdtoc import build, headings, render, render_numbered, slugify

ROOT = Path(__file__).resolve().parent.parent


def run(*args: str, stdin: bytes = b"") -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "python_src/mdtoc.py", *args], cwd=ROOT, input=stdin, capture_output=True)


def test_basic_render() -> None:
    text = "# Title\n## Install\n### From source\n# Title\n"
    assert render(build(text, 1, 6), 1) == (
        "- [Title](#title)\n  - [Install](#install)\n    - [From source](#from-source)\n- [Title](#title-1)\n")


@pytest.mark.parametrize(("line", "expected"), [
    ("#NoSpace", []),
    ("#\tTab", [(1, "Tab")]),
    ("   ### Three", [(3, "Three")]),
    ("    # Four", []),
    ("####### Seven", []),
    ("## Closing ##", [(2, "Closing")]),
    ("## hash#", [(2, "hash#")]),
    ("# ##", []),
    ("# a # #", [(1, "a #")]),
])
def test_atx(line: str, expected: list) -> None:
    assert headings(line) == expected


def test_fences() -> None:
    text = "```\n# no\n```\n``` a`b\n# yes\n~~~~\n# no\n~~~\n# no\n~~~~\n# end\n"
    assert headings(text) == [(1, "yes"), (1, "end")]


def test_unclosed_fence_hides_rest() -> None:
    assert headings("# a\n```\n# b\n") == [(1, "a")]


def test_splitlines_boundaries() -> None:
    assert [t for _, t in headings("# a\x0b# b\x1c# c\u2028# d")] == ["a", "b", "c", "d"]


def test_strip_is_unicode() -> None:
    assert headings("# \x1fx\u2003") == [(1, "x")]


@pytest.mark.parametrize(("title", "slug"), [
    ("Hello, World!", "hello-world"),
    ("İstanbul", "istanbul"),  # lower() 가 만든 결합 점(U+0307)은 \w 가 아니라 지워진다
    ("한글 제목: 설치", "한글-제목-설치"),
    ("under_score and-dash", "under_score-and-dash"),
    ("emoji 🎉 party", "emoji--party"),
    ("x\xa0y", "xy"),
])
def test_slugify(title: str, slug: str) -> None:
    assert slugify(title, {}, set()) == slug


def test_duplicates_count_filtered_headings() -> None:
    entries = build("# A\n## A\n", 2, 6)
    assert entries == [{"level": 2, "text": "A", "slug": "a-1"}]


def test_anchors_never_collide() -> None:
    assert [e["slug"] for e in build("# A\n## a\n# a-1\n# a\n", 1, 6)] == ["a", "a-1", "a-1-1", "a-2"]


def test_numbered() -> None:
    entries = build("# A\n## B\n## C\n# D\n### E\n## F\n", 1, 6)
    assert render_numbered(entries, 1) == (
        "1. [A](#a)\n   1. [B](#b)\n   2. [C](#c)\n2. [D](#d)\n      1. [E](#e)\n   1. [F](#f)\n")


def test_cli_json_and_stdin() -> None:
    proc = run("--json", stdin="# 한글 \"q\"\n".encode())
    assert proc.returncode == 0
    assert proc.stdout == '[{"level": 1, "text": "한글 \\"q\\"", "slug": "한글-q"}]\n'.encode()
    assert json.loads(proc.stdout)[0]["text"] == '한글 "q"'


def test_cli_errors() -> None:
    bad = run(stdin=b"\xff")
    assert (bad.returncode, bad.stdout, bad.stderr) == (1, b"", b"mdtoc: error: <stdin>: not valid UTF-8\n")
    assert run("missing.md").returncode == 1
    assert run("--min-level", "3", "--max-level", "2").returncode == 2
    assert run("--js").returncode == 2
