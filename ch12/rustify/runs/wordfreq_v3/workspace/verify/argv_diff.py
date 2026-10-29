"""인자 해석 차이 검사: 기준 구현(argparse)과 Rust 의 종료 코드·성공 시 stdout 을 비교한다.

사용: python3 verify/argv_diff.py
"""

import itertools
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "python_src"))
import io  # noqa: E402
from contextlib import redirect_stderr, redirect_stdout  # noqa: E402

import wordfreq  # noqa: E402

RUST = os.path.join(ROOT, "rust_app", "target", "release", "wordfreq")
FILE = "tests/fixtures/basic.txt"
TOKENS = [
    FILE, FILE + "/", "--top", "--to", "--t", "--js", "--json", "--he", "--help", "-h", "-hx",
    "--", "--=x", "--top=2", "--t=2", "--json=1", "2", "0", "-", "-5", "-x", "--bogus", "-j", "-t2",
]


def python_result(argv):
    out_raw = io.BytesIO()
    out = io.TextIOWrapper(out_raw, encoding="utf-8", newline="\n")
    err = io.TextIOWrapper(io.BytesIO(), encoding="utf-8", newline="\n")
    with redirect_stdout(out), redirect_stderr(err):
        try:
            code = wordfreq.main(argv)
        except SystemExit as exc:
            code = exc.code
        out.flush()
        err.flush()
    return code, out_raw.getvalue().decode(), err.buffer.getvalue().decode()


def main():
    bad = 0
    total = 0
    err_diff = []
    for n in range(1, 4):
        for argv in itertools.product(TOKENS, repeat=n):
            argv = list(argv)
            total += 1
            pcode, pout, perr = python_result(argv)
            proc = subprocess.run([RUST, *argv], cwd=ROOT, capture_output=True)
            if "-h" in argv or "--help" in argv:
                same_out = True  # 도움말 문구는 비교하지 않는다
            else:
                same_out = proc.stdout.decode() == pout
            if "-h" not in argv and "--help" not in argv and proc.stderr.decode() != perr:
                err_diff.append(argv)  # stderr 문구는 계약상 비교 안 함. 참고용으로만 센다
            if proc.returncode != pcode or not same_out:
                bad += 1
                print("DIFF", argv, pcode, proc.returncode)
    print(f"{total - bad}/{total} argv combinations match")
    print(f"stderr text differs (not compared by contract): {len(err_diff)}; examples: {err_diff[:5]}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
