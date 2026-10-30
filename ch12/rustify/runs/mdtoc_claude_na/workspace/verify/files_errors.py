"""파일 읽기 오류(메시지 포함)와 UTF-8 이 아닌 파일 이름을 Python 과 Rust 로 비교한다."""

import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PY = [sys.executable, str(ROOT / "python_src" / "mdtoc.py")]
BIN = [str(ROOT / "rust_app" / "target" / "release" / "mdtoc")]


def both(args):
    py = subprocess.run([*PY, *args], capture_output=True, input=b"")
    rs = subprocess.run([*BIN, *args], capture_output=True, input=b"")
    return py, rs


def main():
    bad = 0
    with tempfile.TemporaryDirectory() as d:
        d = os.fsencode(d)
        good = d + b"/good.md"
        Path(os.fsdecode(good)).write_bytes(b"# Hi\n")
        weird = d + b"/\xff\xfe-name.md"
        Path(os.fsdecode(weird)).write_bytes("# 제목\n".encode())
        noperm = d + b"/noperm.md"
        Path(os.fsdecode(noperm)).write_bytes(b"# x\n")
        os.chmod(noperm, 0)
        longname = d + b"/" + b"a" * 300
        loop = d + b"/loop"
        os.symlink(b"loop", loop)
        notdir = good + b"/x"
        cases = {"missing": d + b"/missing.md", "dir": d, "noperm": noperm, "weird": weird, "empty": b"",
                 "toolong": longname, "symlink-loop": loop, "not-a-dir": notdir, "good": good,
                 "dev-null": b"/dev/null"}
        for label, path in cases.items():
            py, rs = both([path])
            # 파일 이름에 임시 폴더가 들어가므로 UTF-8 로 해석 못 하는 바이트는 backslashreplace 로 맞춰 비교한다
            same = py.returncode == rs.returncode and py.stdout == rs.stdout
            msg_same = py.stderr.decode("utf-8", "replace") == rs.stderr.decode("utf-8", "replace")
            print(f"{label:13} py={py.returncode} rs={rs.returncode} stdout_same={same} stderr_same={msg_same}")
            if not same:
                bad += 1
            if not msg_same:
                print("   py:", py.stderr[-120:])
                print("   rs:", rs.stderr[-120:])
        os.chmod(noperm, 0o600)
    print("FAIL" if bad else "OK (종료 코드·stdout 일치)", bad)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
