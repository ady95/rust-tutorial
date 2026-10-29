"""Python int(str) 가 쓰는 문자 집합(127 이상의 공백, 10진 숫자와 값)을 전체 코드 포인트에서 뽑아 출력한다."""

import re

spaces = [cp for cp in range(127, 0x110000) if not 0xD800 <= cp <= 0xDFFF and chr(cp).isspace()]
print("spaces >=127:", [hex(c) for c in spaces])
digit = re.compile(r"\d")
mismatch = [cp for cp in range(0x110000) if not 0xD800 <= cp <= 0xDFFF
            and bool(digit.fullmatch(chr(cp))) != chr(cp).isdecimal()]
print("re \\d != isdecimal:", mismatch)
# 10진 숫자 블록이 모두 0부터 시작하는 10자 묶음인지(값 = (cp - 블록 시작) % 10)
bad = []
start = None
for cp in range(0x110000):
    if 0xD800 <= cp <= 0xDFFF:
        continue
    ch = chr(cp)
    if ch.isdecimal():
        if start is None:
            start = cp
        if int(ch) != (cp - start) % 10:
            bad.append(hex(cp))
    else:
        start = None
print("value != (cp - range start) % 10:", bad)
