"""re 의 \\d(str 패턴)가 받는 코드 포인트 범위를 Rust 배열 문법으로 출력한다(cli.rs 의 DECIMAL_RANGES)."""

import re

digit = re.compile(r"\d")
ranges: list[list[int]] = []
for cp in range(0x110000):
    if 0xD800 <= cp <= 0xDFFF:
        continue
    if digit.fullmatch(chr(cp)):
        if ranges and ranges[-1][1] == cp - 1:
            ranges[-1][1] = cp
        else:
            ranges.append([cp, cp])
print(len(ranges))
line = ""
for a, b in ranges:
    item = f"(0x{a:X}, 0x{b:X}), "
    if len(line) + len(item) > 100:
        print("    " + line.rstrip())
        line = ""
    line += item
print("    " + line.rstrip())
