"""Python 의 unicodedata/str 메서드에서 Unicode 표를 뽑아 rust_app/src/unicode_tables.rs 를 만든다.

    python3 verify/gen_unicode_tables.py

표는 isspace, isalnum(re 의 \\w), lower() 전체 매핑, Final_Sigma 용 글자 분류, 십진 숫자(int(), \\d)다.
"""

from __future__ import annotations

import sys
import unicodedata
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "rust_app" / "src" / "unicode_tables.rs"
SURROGATES = range(0xD800, 0xE000)
# Final_Sigma 분류 값
SKIP, CASED = 1, 2


def ranges(points: list[int]) -> list[tuple[int, int]]:
    out: list[tuple[int, int]] = []
    for p in points:
        if out and out[-1][1] + 1 == p:
            out[-1] = (out[-1][0], p)
        else:
            out.append((p, p))
    return out


def sigma_class(c: int) -> int:
    ch = chr(c)
    after_cased = ("A" + ch + "Σ").lower().endswith("ς")
    after_digit = ("1" + ch + "Σ").lower().endswith("ς")
    if after_cased and not after_digit:
        return SKIP
    if after_cased and after_digit:
        return CASED
    return 0


def emit_ranges(name: str, rs: list[tuple[int, int]], lines: list[str]) -> None:
    lines.append(f"pub static {name}: &[(u32, u32)] = &[")
    for i in range(0, len(rs), 6):
        lines.append("    " + " ".join(f"(0x{a:X}, 0x{b:X})," for a, b in rs[i:i + 6]))
    lines.append("];")
    lines.append("")


def main() -> int:
    codes = [c for c in range(0x110000) if c not in SURROGATES]
    space = ranges([c for c in codes if chr(c).isspace()])
    alnum = ranges([c for c in codes if chr(c).isalnum()])

    lower: list[tuple[int, int, int]] = []
    for c in codes:
        if c == 0x3A3:
            continue
        s = chr(c).lower()
        if s != chr(c):
            assert len(s) <= 2, hex(c)
            lower.append((c, ord(s[0]), ord(s[1]) if len(s) == 2 else 0))

    skip = ranges([c for c in codes if sigma_class(c) == SKIP])
    cased = ranges([c for c in codes if sigma_class(c) == CASED])

    # 십진 숫자는 연속한 0~9 열 개씩 묶인다고 가정하고 확인한다
    zeros = []
    for c in codes:
        if unicodedata.decimal(chr(c), None) == 0:
            for k in range(10):
                assert unicodedata.decimal(chr(c + k), None) == k, hex(c)
            zeros.append(c)
    decimals = [c for c in codes if unicodedata.decimal(chr(c), None) is not None]
    assert len(decimals) == 10 * len(zeros)

    lines = [
        f"// 생성 파일 (verify/gen_unicode_tables.py). 손으로 고치지 않는다. "
        f"Python {sys.version.split()[0]}, unidata_version {unicodedata.unidata_version}",
        "",
    ]
    emit_ranges("SPACE", space, lines)
    emit_ranges("ALNUM", alnum, lines)
    emit_ranges("SIGMA_SKIP", skip, lines)
    emit_ranges("SIGMA_CASED", cased, lines)
    lines.append("pub static DECIMAL_ZEROS: &[u32] = &[")
    for i in range(0, len(zeros), 8):
        lines.append("    " + " ".join(f"0x{z:X}," for z in zeros[i:i + 8]))
    lines.append("];")
    lines.append("")
    lines.append("/// (글자, 소문자 첫 글자, 둘째 글자 또는 0). U+03A3 은 문맥이 필요해서 뺀다.")
    lines.append("pub static LOWER: &[(u32, u32, u32)] = &[")
    for i in range(0, len(lower), 4):
        lines.append("    " + " ".join(f"(0x{a:X}, 0x{b:X}, 0x{c:X})," for a, b, c in lower[i:i + 4]))
    lines.append("];")
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {OUT} (python {sys.version.split()[0]}, unidata {unicodedata.unidata_version}): "
          f"space={len(space)} alnum={len(alnum)} lower={len(lower)} skip={len(skip)} cased={len(cased)} "
          f"decimal zeros={len(zeros)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
