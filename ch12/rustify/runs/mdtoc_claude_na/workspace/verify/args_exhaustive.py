"""명령줄 토큰 조합(길이 0~3)을 전부 Python 기준 구현(프로세스 안에서 main 호출)과 Rust 로 비교한다.

비교: 종료 코드, 정상 종료일 때 stdout(도움말 본문 제외), 종료 코드 2 일 때 stderr 가 비어 있지 않은지.
"""

import io
import itertools
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "python_src"))
import mdtoc  # noqa: E402

BIN = str(ROOT / "rust_app" / "target" / "release" / "mdtoc")
MD = b"# A\n## B\n### C\n#### D\n"
POOL = ["--json", "--numbered", "--min-level", "--max-level", "2", "7", "-", "--", "-h", "--help", "--bogus",
        "-x", "-1", "a", "--min-level=3", "--json=1", "-hx", "x y", "-1.5", "--min", "", "٣", "--max-level=2",
        "-h=x", "-hh", "--numbered=", "-.5", "-x y", "--min-level=", "3"]


def py_run(args):
    stdin = io.TextIOWrapper(io.BytesIO(MD))
    out = io.TextIOWrapper(io.BytesIO(), encoding="utf-8")
    err = io.TextIOWrapper(io.BytesIO(), encoding="utf-8")
    old = sys.stdin, sys.stdout, sys.stderr
    sys.stdin, sys.stdout, sys.stderr = stdin, out, err
    try:
        try:
            code = mdtoc.main(list(args))
        except SystemExit as e:
            code = e.code if isinstance(e.code, int) else 1
        out.flush()
        err.flush()
        return code, out.buffer.getvalue(), err.buffer.getvalue()
    finally:
        sys.stdin, sys.stdout, sys.stderr = old


def main():
    bad = total = 0
    for n in range(4):
        for args in itertools.product(POOL, repeat=n):
            total += 1
            pcode, pout, perr = py_run(args)
            p = subprocess.run([BIN, *args], input=MD, capture_output=True)
            ok = p.returncode == pcode
            if ok and pcode == 0 and not pout.startswith(b"usage"):
                ok = p.stdout == pout
            if ok and pcode == 2:
                ok = bool(p.stderr) and bool(perr)
            if ok and pcode == 0 and pout.startswith(b"usage"):
                ok = p.stdout.startswith(b"usage")
            if not ok:
                bad += 1
                if bad <= 30:
                    print("MISMATCH", list(args), "py", pcode, pout[:40], "rust", p.returncode, p.stdout[:40])
    print(f"{total} cases, {bad} mismatches")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
