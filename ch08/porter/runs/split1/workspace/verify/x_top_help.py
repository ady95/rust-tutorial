"""R3: --top 값 전수(U+0000-U+00FF 한 글자, Python \\d 전체, 숫자 경계) / R4: 도움말과 COLUMNS."""
from __future__ import annotations

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from x_lib import ENV, ROOT, both, judge, parallel, run_py, run_rs  # noqa: E402

FS = os.path.join(ROOT, "verify", "x_work_top")


def setup():
    os.makedirs(FS, exist_ok=True)
    # 빈도가 서로 다른 단어 25개 (w1..w25, wk 는 k번) → --top 값이 출력 줄 수로 드러난다
    words = []
    for k in range(1, 26):
        words += [f"w{k}"] * k
    with open(os.path.join(FS, "f.txt"), "w") as fp:
        fp.write(" ".join(words) + "\n")


def values():
    vals = []
    for c in range(0x100):
        if c == 0:
            continue
        vals.append(chr(c))
        vals.append("1" + chr(c))
        vals.append(chr(c) + "1")
    digits = [chr(c) for c in range(0x110000) if not 0xD800 <= c <= 0xDFFF and re.match(r"\d", chr(c))]
    vals += digits
    vals += ["1" + d for d in digits]
    for c in range(0x100, 0x110000, 97):
        if not 0xD800 <= c <= 0xDFFF:
            vals.append(chr(c))
    for n in range(0, 30):
        vals.append(str(n))
        vals.append("0" * 3 + str(n))
    for k in range(15, 25):
        vals += ["9" * k, "1" + "0" * (k - 1), "0" + "9" * k, "1" * k]
    vals += ["9" * 5000, "0" * 5000, "0" * 5000 + "3", "18446744073709551615", "18446744073709551616",
             "9223372036854775807", "9223372036854775808", "4294967295", "4294967296",
             "+3", " 3", "3 ", "-1", "", "1_0", "0x10", "1e3", "3.0", "٣", "２", "Ⅲ", "³", "¹",
             "3\n", "\t3", "3\x00"]
    return vals


def check(v):
    out = []
    try:
        b = v.encode("utf-8")
    except UnicodeEncodeError:
        return out
    if b"\x00" in b:
        return out
    for args in ([b"f.txt", b"--top", b], [b"f.txt", b"--top=" + b], [b"--top", b, b"f.txt"]):
        py, rs = both(args, cwd=FS)
        why = judge(py, rs)
        if why:
            out.append((args, why, py, rs))
    return out


def help_columns():
    out = []
    for cols in (None, "1", "10", "20", "30", "40", "50", "60", "70", "79", "80", "81", "100", "200", "0", "-5", "abc"):
        env = dict(ENV)
        if cols is not None:
            env["COLUMNS"] = cols
        for args in ([b"-h"], [b"f.txt", b"--top", b"0"]):
            py = run_py(args, cwd=FS, env=env)
            rs = run_rs(args, cwd=FS, env=env)
            out.append((cols, args, py, rs, judge(py, rs)))
    return out


def main():
    setup()
    vals = values()
    res = parallel(check, vals, workers=16)
    bad = [x for r in res for x in r]
    print("top values", len(vals), "runs", len(vals) * 3, "diffs", len(bad))
    for args, why, py, rs in bad[:30]:
        print("DIFF", repr(args)[:100], why, "\n   py", repr(py)[:300], "\n   rs", repr(rs)[:300])
    for cols, args, py, rs, why in help_columns():
        print("COLUMNS", cols, args, "py", py[0], "rs", rs[0], "->", why or "same")
        if why and args == [b"-h"]:
            print("   py stdout", py[1])
            print("   rs stdout", rs[1])


if __name__ == "__main__":
    main()
