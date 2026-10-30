"""mdtoc: Markdown 문서의 제목으로 목차를 만든다 (12장 실습 프로젝트, 기준 구현 1판).

    python mdtoc.py README.md
    python mdtoc.py README.md --min-level 2 --max-level 3
    cat README.md | python mdtoc.py --json

사람이 Python 으로만 개발한 프로그램이다. Rust 버전은 12장의 자동화 도구가 만든다.
"""

from __future__ import annotations

import argparse
import json
import re
import sys

FENCE = re.compile(r" {0,3}(`{3,}|~{3,})(.*)")
HEADING = re.compile(r" {0,3}(#{1,6})(?:[ \t]+(.*))?$")
CLOSING = re.compile(r"(?:^|[ \t]+)#+[ \t]*$")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="mdtoc", description="Make a table of contents from Markdown headings.",
                                     allow_abbrev=False)
    parser.add_argument("file", nargs="?", default="-", help="Markdown file (default: standard input)")
    parser.add_argument("--min-level", type=int, choices=range(1, 7), default=1, metavar="N")
    parser.add_argument("--max-level", type=int, choices=range(1, 7), default=6, metavar="N")
    parser.add_argument("--json", action="store_true", help="print headings as JSON")
    args = parser.parse_args(argv)
    if args.min_level > args.max_level:
        parser.error("--min-level must not be greater than --max-level")
    return args


def headings(text: str) -> list[tuple[int, str]]:
    """코드 블록 밖의 ATX 제목(# ~ ######)을 (수준, 제목) 목록으로."""
    found = []
    fence = None  # 열린 코드 블록의 표시(``` 또는 ~~~ 로 시작하는 문자열)
    for line in text.splitlines():
        m = FENCE.match(line)
        if fence is not None:
            if m and m.group(1)[0] == fence[0] and len(m.group(1)) >= len(fence) and not m.group(2).strip(" \t"):
                fence = None
            continue
        if m and not (m.group(1)[0] == "`" and "`" in m.group(2)):
            fence = m.group(1)
            continue
        m = HEADING.match(line)
        if m:
            title = CLOSING.sub("", m.group(2) or "").strip()
            if title:
                found.append((len(m.group(1)), title))
    return found


def slugify(title: str, seen: dict[str, int]) -> str:
    """GitHub 방식에 가까운 앵커: 소문자로 바꾸고, 글자·숫자·_·-·공백만 남기고, 공백을 - 로. 겹치면 -1, -2."""
    base = re.sub(r"[^\w\- ]", "", title.lower()).replace(" ", "-")
    count = seen.get(base, 0)
    seen[base] = count + 1
    return f"{base}-{count}" if count else base


def build(text: str, min_level: int, max_level: int) -> list[dict]:
    seen: dict[str, int] = {}
    entries = []
    for level, title in headings(text):
        slug = slugify(title, seen)  # 걸러 낼 제목도 앵커 번호에는 들어간다(문서 안의 실제 앵커와 같게)
        if min_level <= level <= max_level:
            entries.append({"level": level, "text": title, "slug": slug})
    return entries


def render(entries: list[dict], min_level: int) -> str:
    return "".join(f"{'  ' * (e['level'] - min_level)}- [{e['text']}](#{e['slug']})\n" for e in entries)


def main(argv: list[str] | None = None) -> int:
    sys.stdout.reconfigure(encoding="utf-8", newline="\n")
    sys.stderr.reconfigure(encoding="utf-8", errors="backslashreplace", newline="\n")
    args = parse_args(sys.argv[1:] if argv is None else argv)
    name = "<stdin>" if args.file == "-" else args.file
    try:
        if args.file == "-":
            data = sys.stdin.buffer.read()
        else:
            with open(args.file, "rb") as fp:
                data = fp.read()
    except OSError as err:
        print(f"mdtoc: error: cannot read {name}: {err.strerror}", file=sys.stderr)
        return 1
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        print(f"mdtoc: error: {name}: not valid UTF-8", file=sys.stderr)
        return 1
    entries = build(text, args.min_level, args.max_level)
    if args.json:
        sys.stdout.write(json.dumps(entries, ensure_ascii=False) + "\n")
    else:
        sys.stdout.write(render(entries, args.min_level))
    return 0


if __name__ == "__main__":
    sys.exit(main())
