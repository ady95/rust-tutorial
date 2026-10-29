"""R4: 음수 모양 판정(\\d 는 Unicode Nd)과 단일 대시 묶음의 비ASCII 경계를 Python/Rust 비교."""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from x_lib import ROOT, both, judge, parallel  # noqa: E402

FS = os.path.join(ROOT, "verify", "x_work_top")

pyd = [c for c in range(0x110000) if not 0xD800 <= c <= 0xDFFF and re.match(r"\d", chr(c))]
# Rust 쪽 표의 경계 바로 바깥 글자도 넣는다
extra = set()
for c in pyd:
    for d in (c - 1, c + 1):
        if 0 <= d < 0x110000 and not 0xD800 <= d <= 0xDFFF:
            extra.add(d)
cands = sorted(set(pyd) | extra)
# Unicode 15.1~17.0 에서 새로 생긴 Nd 블록 후보(Python 15.0 에는 없음)
for lo in (0x10D40, 0x11BF0, 0x11DE0, 0x116D0, 0x16130, 0x16D70, 0x1CCF0, 0x1E5F1, 0x1E950):
    cands += list(range(lo, lo + 10))
cands = sorted(set(cands))


def check(c):
    d = chr(c).encode()
    out = []
    for args in ([b"-" + d], [b"-." + d], [b"-" + d + b"\n"], [b"-1." + d], [b"-" + d + b".5"],
                 [b"f.txt", b"--top", b"-" + d], [b"-h" + d], [b"-" + d + b"h"]):
        py, rs = both(args, cwd=FS)
        why = judge(py, rs)
        if why:
            out.append((args, why, py, rs))
    return out


res = parallel(check, cands, workers=16)
bad = [x for r in res for x in r]
print("chars", len(cands), "runs", len(cands) * 8, "diffs", len(bad))
for args, why, py, rs in bad[:20]:
    print("DIFF", repr(args), why, "\n   py", py, "\n   rs", rs)
