"""argparse·pathlib 경계 입력에서 기준 구현과 Rust 바이너리의 종료 코드·stdout·stderr 를 비교한다.

인자 오류(종료 코드 2)는 stderr 가 비어 있지 않은지만 본다. 도움말(0)은 stdout 문구를 비교하지 않는다.
사용법 (프로젝트 루트에서): python3 verify/edge_args.py rust_app/target/release/wordfreq
"""

import subprocess
import sys

binary = sys.argv[1]
F = "tests/fixtures/basic.txt"
CASES = [
    [F], [F + "/"], [F + "/."], ["tests/fixtures/./basic.txt"], ["./" + F], [""], ["tests/fixtures/"],
    ["nope.txt/"], [F + "/x"], ["--to", "2", F], ["--js", F], ["--t=2", F], ["--top", "0", "--top", "2", F],
    [F, "tests/fixtures/ties.txt"], [F, "--json=1"], [F, "--top"], ["--", "-x"], ["-5"], ["-1.5"], ["-5\n"],
    ["-x.txt"], ["-h="], ["-h=x"], ["-hxyz"], ["-h x"], ["--he"], ["--h=1"], ["--top", "--"], ["--top", "5", "--", F],
    ["-h"], ["-hh"], ["-hx"], ["-h=h"], ["--help=1"], ["-x", "--help"], [F, "--top", "abc", "--help"],
    ["--top", "--", "2", F], [F, "--top", "--"], [F, "--top", "-5"], [F, "--top", "--json"], [F, "--=x"],
    [F, "--top=3", "--json"], [F, "--top", "3", "extra"], ["-", "--top", "1"], ["-x y"], ["--x y"],
    [F, "--top", "9" * 5000], [F, "--top", "999999999999999999"], [F, "--top", "1000000000000000000"],
    ["tests/fixtures/korean.txt", "--json"], ["tests/fixtures/empty.txt"], ["tests/fixtures/invalid_utf8.txt"],
]


def run(cmd):
    p = subprocess.run(cmd, capture_output=True)
    return p.returncode, p.stdout, p.stderr


bad = 0
for args in CASES:
    py = run([sys.executable, "python_src/wordfreq.py", *args])
    rs = run([binary, *args])
    if py[0] == 2 and rs[0] == 2:
        ok = bool(rs[2])
    elif py[0] == 0 and rs[0] == 0 and any(a.startswith(("-h", "--he", "-x")) for a in args):
        ok = True
    else:
        ok = py == rs
    bad += not ok
    label = [a if len(a) < 30 else a[:27] + "..." for a in args]
    print("OK  " if ok else "FAIL", label, "py", py[0], "rs", rs[0])
print("mismatches:", bad)
sys.exit(1 if bad else 0)
