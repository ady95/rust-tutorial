"""비교 케이스(cases.json)와 입력 파일(fixtures/)을 만든다. 사람이 케이스를 고칠 때 이 파일을 고치고 다시 실행한다.

    uv run python tests/make_cases.py

케이스 필드: name, args(명령줄 인자), stdin(표준 입력, 선택), stderr("compare" 기본 | "ignore" | "nonempty").
"""

from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIXTURES = HERE / "fixtures"

FILES: dict[str, bytes] = {
    "basic.md": "# Title\n\nintro\n\n## Install\n\n### From source\n\n## Usage\n\n# Title\n".encode(),
    "fences.md": (
        "# Real\n```\n# not a heading\n```\n~~~~ python\n# no\n~~~\n# still code\n~~~~\n"
        "``` a`b\n# heading after fake fence\n  ```\n## Inside\n   ```   \n## After\n"
        "````\n```\n# no\n````\n### End\n"
    ).encode(),
    "unclosed.md": "# Top\n```\n# hidden\n## hidden too\n".encode(),
    "atx.md": (
        "#NoSpace\n#\tTab title\n   # Three spaces\n    # Four spaces\n####### Seven\n"
        "## Closing ##\n## Closing hash#\n# ##\n#\n# a # #\n###### Six ######   \n"
    ).encode(),
    "unicode.md": (
        "# Ünïcödé Tïtle\n# İstanbul\n# 한글 제목: 설치\n# ẞ Straße\n# ΣΊΣΥΦΟΣ\n"
        "# emoji 🎉 party\n# under_score and-dash\n# Ⅻ roman ½ half\n# x\xa0y\u3000z\n"
    ).encode(),
    "dupes.md": "# A\n## a\n### A!\n# a-1\n## A\n".encode(),
    "lines.md": "# one\r\n# two\r# three\x0b# four\x0c# five\x1c# six\x85# seven\u2028# eight\u2029# nine\n".encode(),
    "strip.md": "# \x1fpadded\x1e\n# \u2003em space\u2003\n# tail\x85\n".encode(),
    "json.md": '# quote " and \\ backslash\n# ctrl \x01 \x7f del\n# </script>\n'.encode(),
    "bom.md": "\ufeff# First\n# Second\n".encode(),
    "empty.md": b"",
    "notext.md": "no headings here\n```\n# code\n```\n".encode(),
    "invalid_utf8.md": b"# ok\n# bad \xff byte\n",
    "levels.md": "# L1\n## L2\n### L3\n#### L4\n##### L5\n###### L6\n## L2b\n".encode(),
}

CASES: list[dict] = [
    {"name": "basic", "args": ["tests/fixtures/basic.md"]},
    {"name": "basic-json", "args": ["tests/fixtures/basic.md", "--json"]},
    {"name": "fences", "args": ["tests/fixtures/fences.md"]},
    {"name": "unclosed-fence", "args": ["tests/fixtures/unclosed.md"]},
    {"name": "atx-rules", "args": ["tests/fixtures/atx.md", "--json"]},
    {"name": "unicode", "args": ["tests/fixtures/unicode.md"]},
    {"name": "unicode-json", "args": ["tests/fixtures/unicode.md", "--json"]},
    {"name": "dupes", "args": ["tests/fixtures/dupes.md"]},
    {"name": "line-boundaries", "args": ["tests/fixtures/lines.md"]},
    {"name": "strip-whitespace", "args": ["tests/fixtures/strip.md", "--json"]},
    {"name": "json-escapes", "args": ["tests/fixtures/json.md", "--json"]},
    {"name": "bom", "args": ["tests/fixtures/bom.md"]},
    {"name": "empty", "args": ["tests/fixtures/empty.md"]},
    {"name": "empty-json", "args": ["tests/fixtures/empty.md", "--json"]},
    {"name": "no-headings", "args": ["tests/fixtures/notext.md"]},
    {"name": "levels-2-3", "args": ["tests/fixtures/levels.md", "--min-level", "2", "--max-level", "3"]},
    {"name": "levels-filtered-dupes", "args": ["tests/fixtures/dupes.md", "--min-level", "2"]},
    {"name": "levels-last-wins", "args": ["tests/fixtures/levels.md", "--max-level", "1", "--max-level", "4"]},
    {"name": "levels-equals", "args": ["tests/fixtures/levels.md", "--min-level=6", "--max-level=6"]},
    {"name": "stdin", "args": [], "stdin": "# From stdin\n## Sub\n"},
    {"name": "stdin-dash", "args": ["-", "--json"], "stdin": "# Dash\n"},
    {"name": "invalid-utf8", "args": ["tests/fixtures/invalid_utf8.md"]},
    {"name": "invalid-utf8-stdin", "args": [], "stdin_hex": "2320c3"},
    {"name": "missing-file", "args": ["tests/fixtures/nope.md"], "stderr": "ignore"},
    {"name": "directory", "args": ["tests/fixtures"], "stderr": "ignore"},
    {"name": "usage-level-range", "args": ["--min-level", "0", "tests/fixtures/basic.md"], "stderr": "nonempty"},
    {"name": "usage-min-gt-max", "args": ["--min-level", "4", "--max-level", "2"], "stderr": "nonempty"},
    {"name": "usage-abbrev", "args": ["--js", "tests/fixtures/basic.md"], "stderr": "nonempty"},
    {"name": "usage-unknown", "args": ["--bogus"], "stderr": "nonempty"},
    {"name": "usage-not-int", "args": ["--max-level", "two"], "stderr": "nonempty"},
    {"name": "help", "args": ["--help"], "stdout": "ignore"},
    # 2판: 번호 목록, 앵커 충돌 방지
    {"name": "numbered", "args": ["tests/fixtures/levels.md", "--numbered"]},
    {"name": "numbered-jumps", "args": ["tests/fixtures/dupes.md", "--numbered"]},
    {"name": "numbered-min-level", "args": ["tests/fixtures/basic.md", "--numbered", "--min-level", "2"]},
    {"name": "numbered-json-wins", "args": ["tests/fixtures/basic.md", "--numbered", "--json"]},
    {"name": "dupes-json", "args": ["tests/fixtures/dupes.md", "--json"]},
]


def main() -> None:
    FIXTURES.mkdir(exist_ok=True)
    for name, data in FILES.items():
        (FIXTURES / name).write_bytes(data)
    (HERE / "cases.json").write_text(json.dumps(CASES, ensure_ascii=False, indent=1) + "\n", encoding="utf-8",
                                     newline="\n")
    print(f"{len(FILES)} fixtures, {len(CASES)} cases")


if __name__ == "__main__":
    main()
