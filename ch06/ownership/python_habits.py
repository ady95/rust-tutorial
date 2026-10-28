"""broken/ 의 Rust 예제 6개에 대응하는 Python 코드. Python에서는 어떻게 동작하는지 보여 준다 (06-1).

사용법: python3 python_habits.py
"""


def count_words(words: list[str]) -> int:
    return len(words)


def report(text: str) -> str:  # E0382 대응: 넘긴 뒤에도 같은 리스트를 다시 쓴다
    words = [w.lower() for w in text.split()]
    total = count_words(words)
    first = words[0]
    return f"{total} {first}"


def drop_rare(counts: dict[str, int], minimum: int) -> None:  # E0502 대응
    for word, n in counts.items():
        if n < minimum:
            del counts[word]


def bump_pair(counts: dict[str, int], a: str, b: str) -> None:  # E0499 대응
    counts[a] = counts.get(a, 0) + 1
    counts[b] = counts.get(b, 0) + 1


def longer(a: str, b: str) -> str:  # E0106 대응
    return b if len(b) > len(a) else a


def normalize(word: str) -> str:  # E0515 대응
    lower = word.lower()
    return lower.strip("!\"#$%&'()*+,-./:;<=>?@[\\]^_`{|}~")


def join_lower(lines: list[str]) -> str:  # E0597 대응
    out = []
    for line in lines:
        lower = line.lower()
        out.append(lower)
    return " ".join(out)


def main() -> None:
    print("report:", report("Apple banana apple"))
    counts = {"apple": 3, "kiwi": 1, "pear": 2}
    try:
        drop_rare(counts, 2)
        print("drop_rare:", counts)
    except RuntimeError as exc:
        print("drop_rare: RuntimeError:", exc)
    pair = {"a": 1}
    bump_pair(pair, "a", "a")
    print("bump_pair(a, a):", pair)
    print("longer:", longer("ab", "abc"))
    print("normalize:", normalize("Hello!"))
    print("join_lower:", join_lower(["A B", "C"]))


if __name__ == "__main__":
    main()
