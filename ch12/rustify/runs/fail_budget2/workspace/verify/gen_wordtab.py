"""Python re 의 \\w 에 해당하는 코드 포인트 범위 표를 rust_app/src/wordtab.rs 로 만든다."""

import re
import sys
from pathlib import Path

word = re.compile(r"\w")
ranges = []
start = None
for cp in range(0x110000):
    ok = 0xD800 <= cp < 0xE000 or bool(word.match(chr(cp)))
    ok = ok and not 0xD800 <= cp < 0xE000
    if ok and start is None:
        start = cp
    elif not ok and start is not None:
        ranges.append((start, cp - 1))
        start = None
if start is not None:
    ranges.append((start, 0x10FFFF))

out = Path(__file__).resolve().parent.parent / "rust_app" / "src" / "wordtab.rs"
lines = [f"// verify/gen_wordtab.py 가 만든 파일(Python {sys.version.split()[0]}, 유니코드 \\w 범위)\n"]
lines.append(f"pub const WORD_RANGES: [(u32, u32); {len(ranges)}] = [\n")
for lo, hi in ranges:
    lines.append(f"    (0x{lo:X}, 0x{hi:X}),\n")
lines.append("];\n")
out.write_text("".join(lines))
print(sys.version, len(ranges))
