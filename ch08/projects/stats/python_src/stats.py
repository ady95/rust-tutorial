"""stats — 숫자 목록 요약 (기준 구현 3판, 08장. 1판은 07-4 실험용).

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
inf·nan(또는 너무 커서 inf 가 되는 수)이 있으면 "stats: error: not a finite number on line <N>: <줄>" 을 쓰고 종료 코드 1.

사용법: python stats.py FILE
"""

import math
import statistics
import sys


def parse(lines: list[str]) -> list[float]:
    numbers = []
    for i, line in enumerate(lines, start=1):
        text = line.strip()
        if not text:
            continue
        try:
            value = float(text)
        except ValueError:
            raise ValueError(f"not a number on line {i}: {text}") from None
        # 1판은 inf·nan 을 그대로 넘겨 statistics.stdev 가 AttributeError 로 죽었다 (07-4)
        if not math.isfinite(value):
            raise ValueError(f"not a finite number on line {i}: {text}")
        numbers.append(value)
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
    except UnicodeDecodeError:
        # 3판: UnicodeDecodeError 는 ValueError 의 하위 클래스라 아래 except 에 잡혀 디코더 메시지가 나왔다(08-2)
        print(f"stats: error: not valid UTF-8: {argv[0]}", file=sys.stderr)
        return 1
    except ValueError as err:
        print(f"stats: error: {err}", file=sys.stderr)
        return 1
    if len(numbers) < 2:
        print("stats: error: need at least 2 numbers", file=sys.stderr)
        return 1
    try:
        out = summarize(numbers)
    except OverflowError:
        # 3판: 표준편차가 실수 범위를 넘으면 statistics.stdev 가 OverflowError 로 죽었다(08-2)
        print("stats: error: result out of range", file=sys.stderr)
        return 1
    sys.stdout.write(out)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
