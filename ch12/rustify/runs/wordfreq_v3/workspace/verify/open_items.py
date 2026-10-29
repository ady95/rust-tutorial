"""port_notes 3절의 '확신하지 못하는 부분'을 실행으로 확인한다.

사용: python3 verify/open_items.py
"""

import os
import stat
import subprocess
import sys
import tempfile
import unicodedata

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUST = os.path.join(ROOT, "rust_app", "target", "release", "wordfreq")
PY = ["uv", "run", "python", os.path.join(ROOT, "python_src", "wordfreq.py")]
FILE = "tests/fixtures/basic.txt"


def run(cmd, env=None, stdout=subprocess.PIPE):
    e = dict(os.environ)
    e.update(env or {})
    return subprocess.run(cmd, cwd=ROOT, env=e, stdout=stdout, stderr=subprocess.PIPE)


def both(args, env=None):
    return run(PY + args, env), run([RUST] + args, env)


def main():
    # 1. 실행 사용자 / permission-denied
    print("euid:", os.geteuid())
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "secret.txt")
        with open(p, "w") as f:
            f.write("a b\n")
        os.chmod(p, 0)
        py, rs = both([p])
        print("permission-denied: py", py.returncode, py.stderr, "| rs", rs.returncode, rs.stderr)
        print("  ->", "same" if (py.returncode, py.stderr) == (rs.returncode, rs.stderr) else "DIFF")
        os.chmod(p, stat.S_IRUSR | stat.S_IWUSR)

    # 2. 도움말 쓰기 실패 (/dev/full)
    with open("/dev/full", "wb") as full:
        py = run(PY + ["-h"], stdout=full)
        rs = run([RUST, "-h"], stdout=full)
    print("help to /dev/full: py", py.returncode, py.stderr[-80:], "| rs", rs.returncode, rs.stderr)
    print("  ->", "both nonzero" if py.returncode and rs.returncode else "DIFF")
    for name, cmd in (("py", PY), ("rs", [RUST])):
        r, w = os.pipe()
        os.close(r)  # 읽는 쪽이 이미 닫힌 파이프
        proc = subprocess.run(cmd + ["-h"], cwd=ROOT, stdout=w, stderr=subprocess.PIPE)
        os.close(w)
        print("help to closed pipe:", name, proc.returncode)

    # 3. 도움말 줄바꿈 (COLUMNS)
    diffs = []
    for cols in list(range(1, 121)):
        py, rs = both(["-h"], {"COLUMNS": str(cols)})
        if py.stdout != rs.stdout:
            diffs.append(cols)
    print("help differs for COLUMNS values:", diffs)

    # 6. 경로: //a, 앞뒤 가장자리
    base = os.path.join(ROOT, FILE)
    for arg in ["/" + base, base + "/", base + "/.", os.path.join(ROOT, "tests", ".", "fixtures", "basic.txt"),
                "//" + base, "///" + base, "/" + base + "//"]:
        py, rs = both([arg])
        same = (py.returncode, py.stdout, py.stderr) == (rs.returncode, rs.stdout, rs.stderr)
        print("path", repr(arg[-40:]), "py", py.returncode, "rs", rs.returncode, "same" if same else "DIFF")

    # 7. Unicode 버전
    print("python3 unidata:", unicodedata.unidata_version, "sys", sys.version.split()[0])
    out = run(["uv", "run", "python", "-c", "import unicodedata,sys;print(unicodedata.unidata_version, sys.version.split()[0])"])
    print("uv python:", out.stdout.decode().strip())


if __name__ == "__main__":
    main()
