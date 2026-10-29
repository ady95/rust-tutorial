"""Python 의 \\w(isalnum 또는 _)와 십진 숫자 표를 rust_app/src/tables.rs 로 만든다."""
import os
import sys
import unicodedata

out = os.path.join(os.path.dirname(__file__), "..", "rust_app", "src", "tables.rs")

ranges = []
start = None
for c in range(0x110000):
    ok = chr(c).isalnum() or c == 0x5F
    if ok and start is None:
        start = c
    elif not ok and start is not None:
        ranges.append((start, c - 1))
        start = None
if start is not None:
    ranges.append((start, 0x10FFFF))

# 십진 숫자(int() 가 받는 글자): 0 에 해당하는 코드 포인트 목록
zeros = [c for c in range(0x110000) if unicodedata.category(chr(c)) == "Nd" and unicodedata.decimal(chr(c)) == 0]
for z in zeros:
    assert all(unicodedata.decimal(chr(z + i)) == i for i in range(10))

def to_ranges(pred):
    res = []
    begin = None
    for c in range(0x110000):
        ok = pred(chr(c))
        if ok and begin is None:
            begin = c
        elif not ok and begin is not None:
            res.append((begin, c - 1))
            begin = None
    if begin is not None:
        res.append((begin, 0x10FFFF))
    return res


# Python 의 Final_Sigma 규칙이 쓰는 두 성질을 lower() 결과로 알아낸다(Rust 표준 라이브러리는 유니코드 버전이 달라 쓸 수 없다)
# 무시 가능(Case_Ignorable): "aΣ" + c 에서 Σ 가 끝 시그마(ς)가 된다
# 대소문자 있음(Cased, 무시 가능 아님): "1" + c + "Σ" 에서 Σ 가 끝 시그마가 된다
ignorable = to_ranges(lambda ch: ("aΣ" + ch).lower()[1] == "ς")
cased = to_ranges(lambda ch: ("1" + ch + "Σ").lower()[-1] == "ς")

lowers = []
for c in range(0x80, 0x110000):
    ch = chr(c)
    if 0xD800 <= c <= 0xDFFF or c == 0x3A3:
        continue
    low = ch.lower()
    if low != ch:
        lowers.append((c, low))


def write_ranges(fp, name, rs):
    fp.write(f"pub const {name}: &[(u32, u32)] = &[\n")
    for a, b in rs:
        fp.write(f"    (0x{a:X}, 0x{b:X}),\n")
    fp.write("];\n\n")


with open(out, "w", encoding="utf-8") as fp:
    fp.write(f"// verify/gen_tables.py 가 만든 파일 (Python {sys.version.split()[0]}, Unicode {unicodedata.unidata_version})\n\n")
    fp.write("pub const WORD_RANGES: &[(u32, u32)] = &[\n")
    for a, b in ranges:
        fp.write(f"    (0x{a:X}, 0x{b:X}),\n")
    fp.write("];\n\n")
    fp.write("pub const DIGIT_ZEROS: &[u32] = &[\n")
    for z in zeros:
        fp.write(f"    0x{z:X},\n")
    fp.write("];\n\n")
    write_ranges(fp, "CASE_IGNORABLE", ignorable)
    write_ranges(fp, "CASED", cased)
    fp.write("/// Python `str.lower()` 가 바꾸는 비ASCII 글자(Σ 제외)와 결과\n")
    fp.write("pub const LOWER: &[(u32, &str)] = &[\n")
    for c, low in lowers:
        esc = "".join(f"\\u{{{ord(x):X}}}" for x in low)
        fp.write(f'    (0x{c:X}, "{esc}"),\n')
    fp.write("];\n")
