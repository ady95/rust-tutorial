"""R1/R2/R8/R10/R11: 전 코드 포인트(서로게이트 제외)를 여러 문맥에 넣은 파일로 Python/Rust 비교.

파일마다 --top 큰 값으로 텍스트·JSON 두 형식을 실행해 stdout/stderr/종료 코드를 바이트로 비교한다.
다르면 줄 단위 첫 차이와, 원인 코드 포인트를 좁히기 위해 코드 포인트별 재실행을 한다.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from x_lib import ROOT, both, judge, run_py, run_rs  # noqa: E402

DIR = os.path.join(ROOT, "verify", "x_work_text")
CPS = [c for c in range(0x110000) if not 0xD800 <= c <= 0xDFFF]

SIGMA = "Σ"
CONTEXTS = {
    "single": lambda c: f"{c}\n",
    "infix": lambda c: f"a{c}b\n",
    "upper_infix": lambda c: f"A{c}B\n",
    "wrap": lambda c: f"({c}X{c})\n",
    "sig_before": lambda c: f"{c}{SIGMA}\n",
    "sig_ign": lambda c: f"Α{c}{SIGMA}\n",
    "sig_after": lambda c: f"Α{SIGMA}{c}\n",
    "sig_after_cased": lambda c: f"Α{SIGMA}{c}Β\n",
    "sig_double": lambda c: f"{c}{c}{SIGMA}{c}{c}\n",
    "sig_punct": lambda c: f"Α{SIGMA}{c}.\n",
}


def write(name, fn, cps):
    os.makedirs(DIR, exist_ok=True)
    path = os.path.join(DIR, name + ".txt")
    with open(path, "w", encoding="utf-8", newline="") as fp:
        fp.write("".join(fn(chr(c)) for c in cps))
    return path


def compare_file(path, extra):
    args = [os.fsencode(path), b"--top", b"9" * 30] + extra
    return both(args, cwd=ROOT)


def narrow(name, fn, cps):
    """차이가 난 문맥에서 원인 코드 포인트를 이분 탐색이 아닌 블록 분할로 찾는다."""
    found = []
    stack = [cps]
    while stack:
        block = stack.pop()
        path = write("narrow_" + name, fn, block)
        bad = False
        for extra in ([], [b"--json"]):
            py, rs = compare_file(path, extra)
            if judge(py, rs):
                bad = True
                break
        if not bad:
            continue
        if len(block) == 1:
            found.append(block[0])
            if len(found) >= 40:
                break
            continue
        mid = len(block) // 2
        stack.append(block[mid:])
        stack.append(block[:mid])
    return found


def main():
    total_diff = {}
    for name, fn in CONTEXTS.items():
        path = write(name, fn, CPS)
        status = []
        for extra in ([], [b"--json"]):
            py, rs = compare_file(path, extra)
            why = judge(py, rs)
            status.append(why)
            if why:
                pl = py[1].split(b"\n")
                rl = rs[1].split(b"\n")
                for i, (a, b) in enumerate(zip(pl, rl)):
                    if a != b:
                        print(f"  {name} {extra} first diff line {i}: py={a[:200]!r} rs={b[:200]!r}")
                        break
                print(f"  exit py={py[0]} rs={rs[0]} len py={len(py[1])} rs={len(rs[1])} err py={py[2][:200]!r} rs={rs[2][:200]!r}")
        print(name, "lines", len(CPS), "->", status, flush=True)
        if any(status):
            total_diff[name] = narrow(name, fn, CPS)
            print("   culprits", [f"U+{c:04X}" for c in total_diff[name]], flush=True)
    print("contexts with diffs:", {k: [f"U+{c:04X}" for c in v] for k, v in total_diff.items()})


if __name__ == "__main__":
    main()
