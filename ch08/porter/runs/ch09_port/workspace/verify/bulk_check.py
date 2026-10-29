"""Rust 라이브러리 함수를 Python 과 대량·전수로 대조한다(rust_app/examples/pyprobe.rs 사용).

사용법: python3 verify/bulk_check.py [help|int|repr|rate ...]   (인자가 없으면 전부)
먼저 cargo build --release --examples 로 pyprobe 를 만든다.
"""

from __future__ import annotations

import argparse
import math
import random
import struct
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROBE = ROOT / "rust_app" / "target" / "release" / "examples" / "pyprobe"
sys.path.insert(0, str(ROOT / "python_src"))
import logstat  # noqa: E402

CLAMP = 1 << 40


def probe(requests: list[str]) -> list[str]:
    p = subprocess.run([str(PROBE)], input=("\n".join(requests) + "\n").encode(), capture_output=True, check=True)
    return p.stdout.decode().split("\n")[:-1]


def report(name: str, items: list, expected: list[str], got: list[str]) -> bool:
    assert len(expected) == len(got) == len(items), (len(expected), len(got), len(items))
    bad = [(i, e, g) for i, e, g in zip(items, expected, got) if e != g]
    print(f"{'OK  ' if not bad else 'FAIL'} {name}: {len(items) - len(bad)}/{len(items)} match")
    for i, e, g in bad[:10]:
        print(f"     input={i!r}\n       python={e!r}\n       rust  ={g!r}")
    return not bad


def check_help() -> bool:
    widths = list(range(-500, 3001)) + [10**6, 10**12, CLAMP, CLAMP + 5]
    expected = []
    for c in widths:
        parser = logstat.build_parser()
        parser.formatter_class = lambda prog, c=c: argparse.HelpFormatter(prog, width=c - 2)
        expected.append(parser.format_help().encode().hex())
    # 이 범위 밖(폭 > 2^40)은 Rust 가 2^40 으로 묶는다. Python 출력은 폭이 충분히 크면 같다
    return report("help_text(columns)", widths, expected, probe([f"help {c}" for c in widths]))


def py_int(s: str) -> str:
    try:
        v = int(s)
    except ValueError:
        return "ERR"
    return str(max(-CLAMP, min(CLAMP, v)))


def check_int() -> bool:
    texts = []
    for cp in range(1, 0x110000):
        if 0xD800 <= cp <= 0xDFFF:
            continue
        c = chr(cp)
        texts += [c, "1" + c, c + "1", "1" + c + "2"]
    texts += ["", " ", "1_000", "_1", "1_", "1__0", "+1", "-1", "--1", "+-1", " -12 ", "\t\n\v\f\r7\r\n", "\x1c7",
              "7\x1c　", "-　 1", "1" * 4300, "1" * 4301, "1_" * 4300 + "1", "1_" * 4299 + "1",
              "0" * 4301, "-" + "1" * 4300, "99999999999999999999999", "-99999999999999999999999", "١_٢", "0x10",
              "1e3", "1.0", "\u00851 ", "٠٠٧", "𝟎𝟏𝟐", "+_1", "1 2"]
    expected = [py_int(t) for t in texts]
    return report("python_int(COLUMNS)", texts, expected, probe([f"int {t.encode().hex()}" for t in texts]))


def bits(x: float) -> int:
    return struct.unpack("<Q", struct.pack("<d", x))[0]


def check_repr() -> bool:
    rng = random.Random(20261029)
    values: set[int] = set()
    # 모든 유한 비트 패턴에서 무작위
    while len(values) < 3_000_000:
        b = rng.getrandbits(64)
        if (b >> 52) & 0x7FF != 0x7FF:
            values.add(b)
    # 지연값 범위 [0, 1e9] 의 비트 패턴에서 무작위(양수 실수는 비트 순서 = 값 순서)
    hi = bits(1e9)
    for _ in range(2_000_000):
        values.add(rng.randrange(0, hi + 1))
    # 10의 거듭제곱과 2의 거듭제곱 주변 ±200 ulp(지수 표기 전환 경계 포함)
    for e in range(-324, 309):
        for base in (10.0 ** e if e > -324 else 5e-324,):
            if base == 0 or math.isinf(base):
                continue
            b0 = bits(base)
            values.update(b0 + d for d in range(-200, 201) if 0 <= b0 + d < 0x7FF0000000000000)
    for e in range(-1074, 1024):
        b0 = bits(math.ldexp(1.0, e))
        values.update(b0 + d for d in range(-20, 21) if 0 <= b0 + d < 0x7FF0000000000000)
    # 소수 셋째 자리까지의 값(fuzz 가 만드는 모양), 0~100000 전부
    values.update(bits(round(i / 1000, 3)) for i in range(0, 100_001))
    # 최단 자릿수 동률이 몰리는 짧은 이진 소수 i / 2^j (정확한 십진 전개가 짧다)
    for _ in range(1_200_000):
        j = rng.randrange(0, 80)
        i = rng.randrange(1, 1 << rng.randrange(1, 54))
        x = math.ldexp(float(i), -j)
        if x < 1e17:
            values.add(bits(x))
    # 음수 부호도
    values.update(b | (1 << 63) for b in list(values)[:200_000])
    items = sorted(values)
    expected = [repr(struct.unpack("<d", struct.pack("<Q", b))[0]) for b in items]
    ok = True
    for start in range(0, len(items), 1_000_000):
        chunk = items[start:start + 1_000_000]
        got = probe([f"repr {b:016x}" for b in chunk])
        ok &= report(f"py_repr chunk {start // 1_000_000}", [hex(b) for b in chunk],
                     expected[start:start + 1_000_000], got)
    return ok


def check_rate(max_n: int = 3000) -> bool:
    items = [(e, n) for n in range(1, max_n + 1) for e in range(n + 1)]
    expected = [f"{e / n * 100:.1f}%" for e, n in items]
    ok = True
    for start in range(0, len(items), 1_000_000):
        chunk = items[start:start + 1_000_000]
        ok &= report(f"error_rate chunk {start // 1_000_000}", chunk, expected[start:start + 1_000_000],
                     probe([f"rate {e} {n}" for e, n in chunk]))
    return ok


CHECKS = {"help": check_help, "int": check_int, "repr": check_repr, "rate": check_rate}
names = sys.argv[1:] or list(CHECKS)
results = [CHECKS[n]() for n in names]
sys.exit(0 if all(results) else 1)
