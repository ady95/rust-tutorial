"""wordfreq: 텍스트 파일의 단어 빈도를 세는 CLI (04장 기준 구현).

동작 계약은 contracts/behavior_spec.md 에 있다. 이 파일이 그 계약의 기준 구현이다.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

EXIT_OK = 0
EXIT_INPUT_ERROR = 1
EXIT_USAGE_ERROR = 2  # argparse 가 쓰는 값과 같다

# 단어 앞뒤에서 떼어 낼 문장 부호. 단어 가운데 있는 것은 남긴다 (don't, e-mail).
PUNCTUATION = "!\"#$%&'()*+,-./:;<=>?@[\\]^_`{|}~" + "“”‘’…·"


@dataclass(frozen=True)
class Report:
    total_words: int
    unique_words: int
    top: list[tuple[str, int]]


def tokenize(text: str) -> list[str]:
    """공백(str.split 기준)으로 자르고, 앞뒤 문장 부호를 떼고, 소문자로 바꾼다."""
    words: list[str] = []
    for raw in text.split():
        word = raw.strip(PUNCTUATION).lower()
        if word:
            words.append(word)
    return words


def count_words(words: list[str], top_n: int) -> Report:
    """빈도 내림차순, 같은 빈도는 단어 오름차순(코드 포인트 순)으로 상위 top_n 개."""
    counter = Counter(words)
    ranked = sorted(counter.items(), key=lambda item: (-item[1], item[0]))
    return Report(
        total_words=len(words),
        unique_words=len(counter),
        top=ranked[:top_n],
    )


def format_text(report: Report) -> str:
    lines = [f"words: {report.total_words}", f"unique: {report.unique_words}"]
    lines += [f"{count}\t{word}" for word, count in report.top]
    return "\n".join(lines) + "\n"


def format_json(report: Report) -> str:
    data = {
        "words": report.total_words,
        "unique": report.unique_words,
        "top": [{"word": word, "count": count} for word, count in report.top],
    }
    return json.dumps(data, ensure_ascii=False, separators=(",", ":")) + "\n"


def positive_int(value: str) -> int:
    try:
        number = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f"not an integer: {value}") from None
    if number < 1:
        raise argparse.ArgumentTypeError(f"must be at least 1: {value}")
    return number


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="wordfreq", description="Count word frequencies.")
    parser.add_argument("file", help="UTF-8 text file")
    parser.add_argument("--top", type=positive_int, default=10, help="number of words (default 10)")
    parser.add_argument("--json", action="store_true", help="print JSON instead of text")
    return parser


def main(argv: list[str] | None = None) -> int:
    # Windows 에서도 출력은 항상 UTF-8, 줄바꿈은 LF 로 고정한다 (계약 3절).
    sys.stdout.reconfigure(encoding="utf-8", newline="\n")
    sys.stderr.reconfigure(encoding="utf-8", newline="\n")

    args = build_parser().parse_args(argv)
    path = Path(args.file)
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        print(f"wordfreq: error: file not found: {args.file}", file=sys.stderr)
        return EXIT_INPUT_ERROR
    except UnicodeDecodeError:
        print(f"wordfreq: error: not valid UTF-8: {args.file}", file=sys.stderr)
        return EXIT_INPUT_ERROR
    except OSError:  # 디렉터리, 권한 없음 등
        print(f"wordfreq: error: cannot read file: {args.file}", file=sys.stderr)
        return EXIT_INPUT_ERROR

    report = count_words(tokenize(text), args.top)
    sys.stdout.write(format_json(report) if args.json else format_text(report))
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
