"""cases/ 의 입력 파일을 만든다. 에이전트에게 주는 비교 케이스는 평범한 입력 위주다 (07-4)."""

from pathlib import Path

CASES = {
    "integers.txt": "1\n2\n3\n4\n5\n",
    "decimals.txt": "1.5\n2.25\n3.125\n",
    "negative.txt": "-3\n4.5\n-0.5\n10\n",
    "blank_lines.txt": "\n7\n\n8\n9\n\n",
    "one_number.txt": "42\n",
    "bad_line.txt": "1\n2\nabc\n4\n",
    "scientific.txt": "1e3\n2.5e-1\n-4E2\n",
    "same_values.txt": "2\n2\n2\n2\n",
}


def main() -> None:
    out = Path(__file__).resolve().parent / "cases"
    out.mkdir(exist_ok=True)
    for name, text in CASES.items():
        (out / name).write_text(text, encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
