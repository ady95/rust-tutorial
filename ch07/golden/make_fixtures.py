"""07장 추가 입력 파일을 만든다.

- fixtures/u0295_sigma.txt   : 05-5에서 ch05 run3 이 Python 과 달랐던 입력(ʕ 뒤의 Σ)
- fixtures/new_letters.txt   : 05-5 전체 비교에서 ch04 run1 이 달랐던 코드 포인트 일부로 만든 단어
- fixtures/all_codepoints.txt: 05-5 와 같은 전체 코드 포인트 입력(약 23MB, git 에 넣지 않음)

사용법 (ch07/golden 에서): python3 make_fixtures.py
"""

from pathlib import Path

HERE = Path(__file__).resolve().parent
FIX = HERE / "fixtures"

# 05-5 에서 ch04 run1 의 차이에 관련된 코드 포인트 중 일부 (Unicode 15 이후 대소문자 정보가 바뀌거나 생긴 글자)
NEW_LETTERS = [0x0295, 0x1C8A, 0xA7CB, 0xA7CC, 0xA7CD, 0xA7CF, 0xA7DB, 0x10D70, 0x16EA0]


def words_for(c: str) -> list[str]:
    return [f"A{c}B", f"{c}Σ", f"Σ{c}"]


def main() -> None:
    FIX.mkdir(exist_ok=True)
    (FIX / "u0295_sigma.txt").write_text("ʕΣ ΣΣ ʕ\n", encoding="utf-8", newline="\n")
    words = [w for cp in NEW_LETTERS for w in words_for(chr(cp))]
    (FIX / "new_letters.txt").write_text(" ".join(words) + "\n", encoding="utf-8", newline="\n")
    words = []
    for cp in range(0x110000):
        if 0xD800 <= cp <= 0xDFFF:
            continue
        words += words_for(chr(cp))
    (FIX / "all_codepoints.txt").write_text(" ".join(words) + "\n", encoding="utf-8", newline="\n")
    for f in sorted(FIX.glob("*.txt")):
        print(f"{f.name}: {f.stat().st_size:,} bytes")


if __name__ == "__main__":
    main()
