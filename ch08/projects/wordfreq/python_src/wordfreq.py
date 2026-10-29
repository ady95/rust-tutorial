"""wordfreq: 텍스트 파일의 단어 빈도를 세는 CLI (기준 구현 3판, 08장·11장 이후 결정 반영).

동작 계약은 contracts/behavior_spec.md 에 있다. 이 파일이 그 계약의 기준 구현이다.
1판(04장)과 달라진 점은 계약 끝의 "변경 기록"에 있다.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

EXIT_OK = 0
EXIT_INPUT_ERROR = 1
EXIT_USAGE_ERROR = 2  # argparse 가 쓰는 값과 같다
EXIT_OUTPUT_ERROR = 1

# 단어 앞뒤에서 떼어 낼 문장 부호. 단어 가운데 있는 것은 남긴다 (don't, e-mail).
PUNCTUATION = "!\"#$%&'()*+,-./:;<=>?@[\\]^_`{|}~" + "“”‘’…·"

# --top 이 이보다 큰 자릿수면 그냥 "아주 큰 수"로 본다. 결과는 같고(전체 단어 출력),
# Python int() 의 자릿수 제한(4300자리)에 걸리지 않는다
MAX_TOP_DIGITS = 18


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
    # 계약 1절: ASCII 숫자만. int() 가 받아 주는 전각 숫자·부호·공백·밑줄은 받지 않는다
    if not value or not all("0" <= ch <= "9" for ch in value):
        raise argparse.ArgumentTypeError(f"not an integer: {value}")
    digits = value.lstrip("0")
    if not digits:
        raise argparse.ArgumentTypeError(f"must be at least 1: {value}")
    if len(digits) > MAX_TOP_DIGITS:
        return sys.maxsize
    return int(digits)


def display_name(arg: str) -> str:
    """오류 메시지에 넣을 파일 이름. UTF-8 이 아닌 바이트는 U+FFFD 로 바꾼다 (계약 4절)."""
    return os.fsencode(arg).decode("utf-8", errors="replace")


def build_parser() -> argparse.ArgumentParser:
    # 3판: 옵션 이름 줄여 쓰기(--to)는 받지 않는다(08-2에서 계약에 없던 동작으로 확인)
    parser = argparse.ArgumentParser(prog="wordfreq", description="Count word frequencies.", allow_abbrev=False)
    parser.add_argument("file", help="UTF-8 text file")
    parser.add_argument("--top", type=positive_int, default=10, help="number of words (default 10)")
    parser.add_argument("--json", action="store_true", help="print JSON instead of text")
    return parser


def write_output(text: str) -> bool:
    """stdout 에 쓴다. 파이프가 닫혔거나 디스크가 가득 차면 False (계약 5절)."""
    try:
        sys.stdout.write(text)
        sys.stdout.flush()
    except OSError:
        # 남은 버퍼를 종료할 때 다시 쓰려다 실패하지 않도록 stdout 을 /dev/null 로 돌린다
        devnull = os.open(os.devnull, os.O_WRONLY)
        os.dup2(devnull, sys.stdout.fileno())
        return False
    return True


def main(argv: list[str] | None = None) -> int:
    # Windows 에서도 출력은 항상 UTF-8, 줄바꿈은 LF 로 고정한다 (계약 3절).
    sys.stdout.reconfigure(encoding="utf-8", newline="\n")
    # 3판: 인자 오류 메시지에 UTF-8 이 아닌 바이트(서로게이트)가 들어가도 죽지 않도록 backslashreplace(08-2)
    sys.stderr.reconfigure(encoding="utf-8", errors="backslashreplace", newline="\n")

    args = build_parser().parse_args(argv)
    path = Path(args.file)
    name = display_name(args.file)
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        print(f"wordfreq: error: file not found: {name}", file=sys.stderr)
        return EXIT_INPUT_ERROR
    except UnicodeDecodeError:
        print(f"wordfreq: error: not valid UTF-8: {name}", file=sys.stderr)
        return EXIT_INPUT_ERROR
    except OSError:  # 디렉터리, 권한 없음 등
        print(f"wordfreq: error: cannot read file: {name}", file=sys.stderr)
        return EXIT_INPUT_ERROR

    report = count_words(tokenize(text), args.top)
    if not write_output(format_json(report) if args.json else format_text(report)):
        print("wordfreq: error: cannot write output", file=sys.stderr)
        return EXIT_OUTPUT_ERROR
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
