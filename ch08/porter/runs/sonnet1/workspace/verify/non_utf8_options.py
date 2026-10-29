"""UTF-8 이 아닌 바이트가 든 옵션·--top 값에서 Python 과 Rust 의 종료 코드와 stderr 유무를 비교한다.
사용법 (프로젝트 루트에서): python3 verify/non_utf8_options.py rust_app/target/release/wordfreq
"""

import subprocess
import sys

binary = sys.argv[1]
F = b"tests/fixtures/basic.txt"
CASES = [
    [F, b"--top", b"\xff"],
    [F, b"--top=\xff"],
    [F, b"--\xff"],
    [F, b"-\xff"],
    [F, b"--top", b"1\xff"],
    [F, b"--json=\xff"],
    [F, b"--to\xff"],
    [F, b"\xff", b"--top", b"1"],
    [b"\xff"],
    [F, b"-h\xff"],
    [b"--help=\xff"],
]
for args in CASES:
    res = []
    for cmd in ([sys.executable, b"python_src/wordfreq.py"], [binary.encode()]):
        p = subprocess.run([*cmd, *args], capture_output=True)
        res.append((p.returncode, bool(p.stderr), p.stdout[:20]))
    flag = "same" if res[0][:2] == res[1][:2] else "DIFF"
    print(flag, args[1:] if len(args) > 1 else args, "py", res[0][:2], "rs", res[1][:2])
    if flag == "DIFF":
        p = subprocess.run([sys.executable, b"python_src/wordfreq.py", *args], capture_output=True)
        print("     python stderr tail:", p.stderr.decode("utf-8", "replace").strip().splitlines()[-1:])
