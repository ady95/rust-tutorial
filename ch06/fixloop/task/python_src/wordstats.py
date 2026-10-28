"""wordstats — 단어 통계 (06장 실험용 Python 기준 구현).

표준 입력의 텍스트를 단어로 나눠 요약을 출력한다.
    words: 전체 단어 수
    unique: min 미만을 뺀 서로 다른 단어 수
    longest: 가장 긴 단어(글자 수 기준, 같으면 먼저 나온 것). 없으면 -
    <횟수>\t<단어>  (횟수 내림차순, 같으면 단어 오름차순, 최대 top 줄)

사용법: python wordstats.py [--top N] [--min M] < input.txt
"""

import argparse
import string
import sys


def normalize(word: str) -> str:
    return word.lower().strip(string.punctuation)


def tokenize(text: str) -> list[str]:
    return [w for w in (normalize(t) for t in text.split()) if w]


def count(words: list[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for w in words:
        counts[w] = counts.get(w, 0) + 1
    return counts


def drop_rare(counts: dict[str, int], minimum: int) -> None:
    for w in [w for w, n in counts.items() if n < minimum]:
        del counts[w]


def merge(counts: dict[str, int], source: str, target: str) -> None:
    """source 의 횟수를 target 에 더하고 source 는 지운다. 같은 단어면 그대로 둔다."""
    if source == target or source not in counts:
        return
    counts[target] = counts.get(target, 0) + counts.pop(source)


def longer(a: str, b: str) -> str:
    return b if len(b) > len(a) else a


def longest(words: list[str]) -> str | None:
    best: str | None = None
    for w in words:
        best = w if best is None else longer(best, w)
    return best


def top_n(counts: dict[str, int], n: int) -> list[tuple[str, int]]:
    return sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[:n]


def summary(text: str, top: int, minimum: int) -> str:
    words = tokenize(text)
    counts = count(words)
    drop_rare(counts, minimum)
    lines = [
        f"words: {len(words)}",
        f"unique: {len(counts)}",
        f"longest: {longest(words) or '-'}",
    ]
    lines += [f"{n}\t{w}" for w, n in top_n(counts, top)]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--top", type=int, default=5)
    parser.add_argument("--min", type=int, default=1)
    args = parser.parse_args()
    sys.stdout.write(summary(sys.stdin.read(), args.top, args.min) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
