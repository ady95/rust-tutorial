"""Python str.lower() 와 str.split() 의 기준 표를 만든다 (Rust 이식 점검용, 런타임에는 쓰지 않음).

사용법 (프로젝트 루트에서): uv run python rust_app/tools/lower_table.py OUT_PATH
OUT_PATH 에 "코드포인트<TAB>소문자 코드포인트들" 을 대문자/소문자 변환이 일어나는 글자마다 한 줄씩 쓴다.
첫 줄은 "# unicode <버전>", 둘째 줄은 "# space <공백 코드포인트들>" 이다.
"""

import sys
import unicodedata


def main() -> int:
    out = sys.argv[1]
    lines = [f"# unicode {unicodedata.unidata_version} python {sys.version.split()[0]}"]
    spaces = [c for c in range(0x110000) if chr(c).isspace()]
    lines.append("# space " + " ".join(f"{c:X}" for c in spaces))
    for c in range(0x110000):
        if 0xD800 <= c <= 0xDFFF:
            continue
        low = chr(c).lower()
        if low != chr(c):
            lines.append(f"{c:X}\t" + " ".join(f"{ord(x):X}" for x in low))
    with open(out, "w", encoding="utf-8") as fp:
        fp.write("\n".join(lines) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
