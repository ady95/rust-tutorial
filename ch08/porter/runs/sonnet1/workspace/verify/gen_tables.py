"""Python 3.12(Unicode 15.0)의 동작에서 표를 뽑아 rust_app/src/py_tables.rs 를 만든다.

- SIGMA_IGNORABLE : Final_Sigma 판단에서 건너뛰는 글자(Case_Ignorable). Python 의 동작으로 탐침한다.
    c+"Σ" 가 ς 로 끝나면 (Cased 이고 건너뛰지 않음), "α"+c+"Σ" 가 ς 로 끝나는데 앞의 경우가 아니면 건너뜀.
- SIGMA_CASED     : 건너뛰지 않으면서 Cased 인 글자.
- DIGITS          : 정규식 \\d (= Nd) 에 맞는 글자.
탐침이 맞는지는 verify/sigma_context.py 가 전 코드 포인트로 다시 확인한다.
사용법: python3 verify/gen_tables.py
"""

import re
import sys
import unicodedata
from pathlib import Path

CODEPOINTS = [c for c in range(0x110000) if not 0xD800 <= c <= 0xDFFF]


def ranges(values):
    out = []
    for v in values:
        if out and out[-1][1] + 1 == v:
            out[-1][1] = v
        else:
            out.append([v, v])
    return out


ign, cased = [], []
for cp in CODEPOINTS:
    c = chr(cp)
    a = c.__add__("Σ").lower().endswith("ς")
    b = ("α" + c + "Σ").lower().endswith("ς")
    if a:
        cased.append(cp)
    elif b:
        ign.append(cp)
digits = [cp for cp in CODEPOINTS if re.fullmatch(r"\d", chr(cp))]
assert digits == [cp for cp in CODEPOINTS if unicodedata.category(chr(cp)) == "Nd"]


def table(name, doc, values):
    rs = ranges(values)
    body = "".join(f"    ('\\u{{{lo:X}}}', '\\u{{{hi:X}}}'),\n" for lo, hi in rs)
    return f"/// {doc}\npub const {name}: &[(char, char)] = &[\n{body}];\n\n"


text = "// verify/gen_tables.py 가 만든 파일이다. 직접 고치지 않는다 (Python 3.12.3, Unicode " + unicodedata.unidata_version + ")\n\n"
text += table("SIGMA_IGNORABLE", "Final_Sigma 에서 건너뛰는 글자", ign)
text += table("SIGMA_CASED", "건너뛰지 않는 Cased 글자", cased)
text += table("DIGITS", "정규식 \\d 에 맞는 글자(Nd)", digits)
text += """pub fn in_table(table: &[(char, char)], c: char) -> bool {
    table
        .binary_search_by(|&(lo, hi)| {
            if hi < c {
                std::cmp::Ordering::Less
            } else if lo > c {
                std::cmp::Ordering::Greater
            } else {
                std::cmp::Ordering::Equal
            }
        })
        .is_ok()
}
"""
out = Path(__file__).resolve().parent.parent / "rust_app" / "src" / "py_tables.rs"
out.write_text(text, encoding="utf-8")
print("ignorable", len(ign), len(ranges(ign)), "ranges; cased", len(cased), len(ranges(cased)), "ranges; digits", len(digits))
