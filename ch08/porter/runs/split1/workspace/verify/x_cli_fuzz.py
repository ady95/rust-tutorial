"""R3/R4: argv 를 토큰 알파벳으로 전수 조합(길이 0~3) + 무작위(길이 4~6)로 만들어 Python/Rust 비교.

각 토큰 이름의 파일을 x_work/ 에 만들어 둔다(내용이 달라 어떤 파일을 읽었는지 출력으로 드러남).
"""
from __future__ import annotations

import itertools
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from x_lib import WORK, both, judge, parallel  # noqa: E402

TOKENS = [
    b"f", b"g", b"-", b"--", b"--top", b"--to", b"--t", b"--top=2", b"--top=", b"--t=3",
    b"2", b"0", b"007", b"-5", b"-1.5", b"-.5", b"-5\n", b"--json", b"--js", b"--j",
    b"--json=1", b"--json=", b"-h", b"--help", b"--he", b"-hx", b"-h=1", b"-x", b"-x y",
    b"--=x", b"---", b"-hh", b"-t2", b"--top=-1", "-٣".encode(), b"--x", b" ",
    b"-h-", b"-h--json", b"--top=+3", b"-1e3", b"-5\t", b"--h=1",
]


def setup():
    os.makedirs(WORK, exist_ok=True)
    for i, t in enumerate(TOKENS):
        if b"/" in t or t in (b"", b".", b".."):
            continue
        p = os.path.join(os.fsencode(WORK), t)
        with open(p, "wb") as fp:
            fp.write(b"w%d w%d x\n" % (i, i))


def check(args):
    py, rs = both(list(args))
    why = judge(py, rs)
    return (args, why, py, rs) if why else None


def main():
    setup()
    combos = []
    for n in range(0, 4):
        combos += list(itertools.product(TOKENS, repeat=n))
    rnd = random.Random(20261029)
    for _ in range(int(sys.argv[1]) if len(sys.argv) > 1 else 3000):
        combos.append(tuple(rnd.choice(TOKENS) for _ in range(rnd.randint(4, 6))))
    print("cases", len(combos), flush=True)
    res = parallel(check, combos, workers=16)
    bad = [r for r in res if r]
    print("diffs", len(bad))
    for args, why, py, rs in bad[:60]:
        print(repr(list(args)), why)
        print("   py", py)
        print("   rs", rs)


if __name__ == "__main__":
    main()
