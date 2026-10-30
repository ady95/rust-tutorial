"""Python 3.12 의 유니코드 동작을 Rust 표(rust_app/src/tables.rs)로 뽑아낸다.

Rust 표준 라이브러리의 유니코드 버전·정의가 Python 과 다를 수 있어서(예: is_alphanumeric 은
Other_Alphabetic 결합 문자를 포함한다) 코드 포인트 전체를 Python 으로 조사해 표로 만든다.
"""

import re
import sys
import unicodedata
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "rust_app" / "src" / "tables.rs"
WORD = re.compile(r"\w")
SURR = range(0xD800, 0xE000)


def chars():
    return [c for c in range(0x110000) if c not in SURR]


def ranges(pred):
    out = []
    for cp in chars():
        if pred(cp):
            if out and out[-1][1] == cp - 1:
                out[-1][1] = cp
            else:
                out.append([cp, cp])
    return out


def fmt_ranges(name, rs):
    body = "".join(f"    (0x{a:X}, 0x{b:X}),\n" for a, b in rs)
    return f"pub const {name}: &[(u32, u32)] = &[\n{body}];\n\n"


def sigma_cased(cp):  # 대문자 시그마 앞/뒤에서 "cased 이면서 case-ignorable 이 아닌" 글자
    return "".join(("1" + chr(cp) + "Σ").lower())[-1] == "ς"


def sigma_skip(cp):  # case-ignorable (cased 여부와 무관하게 건너뜀)
    return ("A" + chr(cp) + "Σ").lower()[-1] == "ς" and not sigma_cased(cp)


def main():
    print("python", sys.version.split()[0], "unicode", unicodedata.unidata_version)
    parts = ["// verify/gen_tables.py 가 만든 파일이다. 직접 고치지 않는다.\n"]
    parts.append(f"// Python {sys.version.split()[0]}, Unicode {unicodedata.unidata_version}\n\n")
    parts.append(fmt_ranges("WORD", ranges(lambda cp: WORD.match(chr(cp)) is not None)))
    parts.append(fmt_ranges("DIGIT", ranges(lambda cp: unicodedata.category(chr(cp)) == "Nd")))
    parts.append(fmt_ranges("SIGMA_CASED", ranges(sigma_cased)))
    parts.append(fmt_ranges("SIGMA_SKIP", ranges(sigma_skip)))
    pairs = []
    for cp in chars():
        low = chr(cp).lower()
        if low != chr(cp) and len(low) == 1:
            pairs.append((cp, ord(low)))
        elif len(low) != 1:
            assert cp == 0x130 and low == "i̇", (cp, low)
    body = "".join(f"    (0x{a:X}, 0x{b:X}),\n" for a, b in pairs)
    parts.append(f"pub const LOWER: &[(u32, u32)] = &[\n{body}];\n")
    OUT.write_text("".join(parts), encoding="utf-8")


if __name__ == "__main__":
    main()
