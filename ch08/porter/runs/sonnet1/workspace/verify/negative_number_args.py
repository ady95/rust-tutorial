"""'-'+<글자> 모양 인자를 모든 Unicode 숫자(Nd)와 그 밖 일부 글자로 Python 과 Rust 에 넘겨 종료 코드를 비교한다.
Python 정규식 \\d 는 Nd 전체를 받는다. 비교 대상은 -N, -N.N, -.N 과 끝의 개행.
사용법: python3 verify/negative_number_args.py rust_app/target/release/wordfreq
"""

import re
import subprocess
import sys
import unicodedata

binary = sys.argv[1]
nd = [chr(c) for c in range(0x110000) if unicodedata.category(chr(c)) == "Nd"]
assert all(re.match(r"\d", c) for c in nd)
# \d 가 Nd 와 정확히 같은지 전 코드 포인트로 확인
regex_digits = [chr(c) for c in range(0x110000) if re.fullmatch(r"\d", chr(c))]
print("Nd:", len(nd), "regex \\d:", len(regex_digits), "same:", nd == regex_digits)

args_list = []
for c in nd:
    args_list += [f"-{c}", f"-{c}.{c}", f"-.{c}", f"-{c}\n"]
args_list += ["-a", "-٣x", "-٣.", "-.", "-²", "-①", "-½", "-1.", "-1.5.2"]


def run(cmd):
    p = subprocess.run(cmd, capture_output=True)
    return p.returncode


bad = 0
for arg in args_list:
    py = run([sys.executable, "python_src/wordfreq.py", arg])
    rs = run([binary, arg])
    if py != rs:
        bad += 1
        if bad <= 20:
            print("MISMATCH", repr(arg), "py", py, "rs", rs)
print("tested:", len(args_list), "mismatches:", bad)
sys.exit(1 if bad else 0)
