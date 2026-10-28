"""stats — 숫자 목록 요약 (07-4 실험용 Python 기준 구현).

입력 파일: 한 줄에 숫자 하나(빈 줄은 건너뜀). 출력:
    count: <개수>
    sum: <합계, repr>
    mean: <평균, repr>
    mean2: <평균을 소수 둘째 자리로 round 한 값, repr>
    stdev: <표본 표준편차를 소수 넷째 자리까지 고정 소수점>
    min: <최솟값, repr>
    max: <최댓값, repr>

숫자가 2개 미만이면 stderr 에 "stats: error: need at least 2 numbers" 를 쓰고 종료 코드 1.
숫자가 아닌 줄이 있으면 "stats: error: not a number on line <N>: <줄>" 을 쓰고 종료 코드 1.

사용법: python stats.py FILE
"""

import statistics
import sys


def parse(lines: list[str]) -> list[float]:
    numbers = []
    for i, line in enumerate(lines, start=1):
        text = line.strip()
        if not text:
            continue
        try:
            numbers.append(float(text))
        except ValueError:
            raise ValueError(f"not a number on line {i}: {text}") from None
    return numbers


def summarize(numbers: list[float]) -> str:
    mean = statistics.mean(numbers)
    lines = [
        f"count: {len(numbers)}",
        f"sum: {sum(numbers)!r}",
        f"mean: {mean!r}",
        f"mean2: {round(mean, 2)!r}",
        f"stdev: {statistics.stdev(numbers):.4f}",
        f"min: {min(numbers)!r}",
        f"max: {max(numbers)!r}",
    ]
    return "\n".join(lines) + "\n"


def main(argv: list[str]) -> int:
    sys.stdout.reconfigure(newline="\n")
    sys.stderr.reconfigure(newline="\n")
    if len(argv) != 1:
        print("usage: stats FILE", file=sys.stderr)
        return 2
    try:
        with open(argv[0], encoding="utf-8") as fp:
            numbers = parse(fp.read().splitlines())
    except OSError:
        print(f"stats: error: cannot read file: {argv[0]}", file=sys.stderr)
        return 1
    except ValueError as err:
        print(f"stats: error: {err}", file=sys.stderr)
        return 1
    if len(numbers) < 2:
        print("stats: error: need at least 2 numbers", file=sys.stderr)
        return 1
    sys.stdout.write(summarize(numbers))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
