"""기준 구현(Python)의 Unicode 동작을 표로 뽑아 rust_app/src/unicode_tables.rs 를 만든다.

Rust 툴체인의 Unicode 버전과 무관하게 Python 과 같은 결과를 내기 위해, 아래를 Python 에서 직접 뽑는다.
- LOWER: chr(c).lower() 가 한 글자이고 c 와 다른 글자 (구간 압축: start, end, step, delta)
- LOWER_MULTI: chr(c).lower() 가 여러 글자인 경우
- SIGMA_SKIP / SIGMA_CASED: str.lower() 의 Final_Sigma 판단에 쓰이는 글자 분류.
  CPython 내부 플래그(Case_Ignorable, Cased)를 직접 볼 수 없으므로 lower() 결과로 역산한다.
    X = (c + "Σ").lower() 가 ς 로 끝남  ->  cased(c) and not ignorable(c)
    Y = ("A" + c + "Σ").lower() 가 ς 로 끝남 -> ignorable(c) or cased(c)
    ignorable = Y and not X,  (ignorable 이 아닐 때) cased = X
- SPACE: str.isspace() (str.split() 의 기준)
- DECIMAL: re 의 \\d (argparse 음수 판정 정규식)

사용법: python3 verify/gen_unicode_tables.py
"""

from __future__ import annotations

import re
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "rust_app" / "src" / "unicode_tables.rs"

SIGMA = "Σ"
FINAL = "ς"


def codepoints():
    for c in range(0x110000):
        if 0xD800 <= c <= 0xDFFF:
            continue
        yield c


def ranges(flags: list[int]) -> list[tuple[int, int]]:
    out: list[tuple[int, int]] = []
    for c in flags:
        if out and out[-1][1] + 1 == c:
            out[-1] = (out[-1][0], c)
        else:
            out.append((c, c))
    return out


def lower_runs(pairs: list[tuple[int, int]]) -> list[tuple[int, int, int, int]]:
    """(c, lower) 목록을 (start, end, step, delta) 로 압축한다. step 은 1 또는 2."""
    runs: list[list[int]] = []
    for c, low in pairs:
        delta = low - c
        if runs:
            start, end, step, d = runs[-1]
            if d == delta and start == end and c - end in (1, 2):
                runs[-1] = [start, c, c - end, d]
                continue
            if d == delta and start != end and c - end == step:
                runs[-1][1] = c
                continue
        runs.append([c, c, 1, delta])
    return [tuple(r) for r in runs]  # type: ignore[misc]


def main() -> int:
    lower_pairs: list[tuple[int, int]] = []
    lower_multi: list[tuple[int, str]] = []
    skip: list[int] = []
    cased: list[int] = []
    space: list[int] = []
    decimal: list[int] = []
    digit_re = re.compile(r"\d")
    for c in codepoints():
        ch = chr(c)
        low = ch.lower()
        if low != ch:
            if len(low) == 1:
                lower_pairs.append((c, ord(low)))
            else:
                lower_multi.append((c, low))
        x = (ch + SIGMA).lower().endswith(FINAL)
        y = ("A" + ch + SIGMA).lower().endswith(FINAL)
        if y and not x:
            skip.append(c)
        elif x:
            cased.append(c)
        if ch.isspace():
            space.append(c)
        if digit_re.match(ch):
            decimal.append(c)

    lines = [
        "// 자동 생성 파일: verify/gen_unicode_tables.py 가 기준 구현의 Python 에서 뽑았다. 손으로 고치지 않는다.",
        f"// Python {sys.version.split()[0]}, Unicode {unicodedata.unidata_version}",
        "",
        "#[cfg(test)]",
        f'pub const UNIDATA_VERSION: &str = "{unicodedata.unidata_version}";',
        "",
        "/// (start, end, step, delta): start..=end 에서 step 간격의 글자는 c + delta 로 소문자가 된다",
        "pub const LOWER: &[(u32, u32, u32, i32)] = &[",
    ]
    lines += [f"    (0x{s:04X}, 0x{e:04X}, {st}, {d})," for s, e, st, d in lower_runs(lower_pairs)]
    lines += ["];", "", "/// 소문자가 여러 글자가 되는 글자", "pub const LOWER_MULTI: &[(u32, &str)] = &["]
    for c, low in lower_multi:
        esc = "".join(f"\\u{{{ord(x):04X}}}" for x in low)
        lines.append(f'    (0x{c:04X}, "{esc}"),')
    lines.append("];")
    for name, doc, data in [
        ("SIGMA_SKIP", "Final_Sigma 판단에서 건너뛰는 글자(Case_Ignorable)", skip),
        ("SIGMA_CASED", "Final_Sigma 판단에서 대소문자가 있는 글자(Cased, Case_Ignorable 제외)", cased),
        ("SPACE", "str.isspace() 가 참인 글자", space),
        ("DECIMAL", "정규식 \\d 에 맞는 글자", decimal),
    ]:
        lines += ["", f"/// {doc}", f"pub const {name}: &[(u32, u32)] = &["]
        lines += [f"    (0x{s:04X}, 0x{e:04X})," for s, e in ranges(data)]
        lines.append("];")
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}: lower={len(lower_pairs)} multi={len(lower_multi)} "
          f"skip={len(skip)} cased={len(cased)} space={len(space)} decimal={len(decimal)}")
    print(f"Python {sys.version.split()[0]}, Unicode {unicodedata.unidata_version}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
