"""손으로 만든 가장자리 문서·파일 입출력을 Python 기준 구현과 Rust 바이너리로 비교한다.

    python3 verify/edge_docs.py

종료 코드, stdout, stderr 를 바이트 단위로 비교한다(파일 읽기 오류의 stderr 도 같은 문구다).
읽기 권한 시험은 root 로 실행하면 의미가 없어서 건너뛴다.
"""

from __future__ import annotations

import itertools
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PY = [sys.executable, str(ROOT / "python_src" / "mdtoc.py")]
RS = [str(ROOT / "rust_app" / "target" / "release" / "mdtoc")]

BOUNDARIES = ["\n", "\r\n", "\r", "\x0b", "\x0c", "\x1c", "\x1d", "\x1e", "\x85", " ", " "]
DOCS: list[bytes | str] = [
    "# A\n## a\n# a-1\n",
    "# !!!\n## !!\n# a\n# a-1\n## a\n# a-1\n",
    "\n".join(["# same"] * 8) + "\n",
    "# a #\x1f\n# a #\n# a\t#\n# a ##\t\n#\t#\n# #  #\n# a #b\n# #\n#\n# \n#  x  #  #\n",
    "#　x\n# x　\n# x\n \t# x\n    # x\n\t# x\n#######\n####### x\n",
    "```\n# in\n``` \n# out\n````\n```\n# in\n````\n# out2\n~~~\n# in\n```\n~~~~\n# out3\n",
    "``` a`b\n# yes\n~~~ a`b\n# no\n~~~\n# yes2\n    ```\n# yes3\n\t```\n# yes4\n``` \n# in\n",
    "```\n# never closed\n",
    "~~~~\n~~~\n# in\n~~~~ x\n# in\n~~~~ \n# in\n~~~~ \t\n# out\n",
    "﻿# bom\n# next\n",
    "# mid﻿dle\n# ﻿\n# ​\n# a​b\n",
    "# \x08tab\there\x01\x1f\x7f\x80\x9f\n#  x\n# quote \" back \\ slash / <\n",
    "# İstanbul\n# ΣΊΣΥΦΟΣ\n# AΣ\n# AΣB\n# A.Σ\n# ÁΣ\n# AΣ.\n# ΣΣ\n# 1Σ\n# Σ\n# ẞ Ⅻ ½ ٣ ²\n",
    "# x y z　w\n# áb\n# 🎉 party\n# 한글 제목\n# a_b-c d\n",
    "",
    "\n",
    "no headings\nat all\n",
    b"# bad \xff\n",
    b"# ok\n\xed\xa0\x80\n",
    b"# x\xc0\x80\n",
    b"# x\xf4\x90\x80\x80\n",
    b"# x\xef\xbf\xbe \xef\xbf\xbf\n",
    b"\xff",
    b"# trunc \xe2\x82",
    "# x\r\n## y\r\n### z\r",
]
for sep in BOUNDARIES:
    DOCS.append(f"# a{sep}# b{sep}")
    DOCS.append(f"# a{sep}```{sep}# in{sep}```{sep}# b")
for a, b in itertools.product(BOUNDARIES, repeat=2):
    DOCS.append(f"# a{a}{b}# b{b}{a}")
DOCS.append("# a\n\r# b\r\r\n# c\r\n\r\n")

ARG_SETS = [[], ["--json"], ["--min-level", "2"], ["--max-level", "2", "--json"], ["--min-level=6", "--max-level=6"]]


def run(cmd: list[str], args: list[str], data: bytes) -> tuple[int, bytes, bytes]:
    proc = subprocess.run(cmd + args, input=data, capture_output=True, cwd=ROOT, timeout=120)
    return proc.returncode, proc.stdout, proc.stderr


def main() -> int:
    bad = 0
    total = 0

    def same(label: str, args: list[str], data: bytes = b"") -> None:
        nonlocal bad, total
        total += 1
        py, rs = run(PY, args, data), run(RS, args, data)
        if py != rs:
            bad += 1
            print(f"MISMATCH {label} {args!r}\n  python={py!r}\n  rust  ={rs!r}")

    for doc in DOCS:
        data = doc if isinstance(doc, bytes) else doc.encode("utf-8")
        for args in ARG_SETS:
            same(repr(doc)[:60], args, data)

    with tempfile.TemporaryDirectory() as tmp:
        t = Path(tmp)
        (t / "한글.md").write_text("# 파일\n## x\n", encoding="utf-8")
        (t / "bad utf8.md").write_bytes(b"# \xff\n")
        (t / "-").write_text("# literal dash file\n", encoding="utf-8")
        (t / "empty.md").write_bytes(b"")
        (t / "sub").mkdir()
        (t / "locked.md").write_text("# locked\n", encoding="utf-8")
        (t / "locked.md").chmod(0)
        names = ["한글.md", "bad utf8.md", "empty.md", "sub", "missing.md", "locked.md", "", "-", "sub/", "empty.md/x"]
        for name in names:
            os.chdir(t)
            for cmd_args in ([name], [name, "--json"]):
                total += 1
                py = subprocess.run(PY + cmd_args, capture_output=True, cwd=t, input=b"# stdin\n")
                rs = subprocess.run(RS + cmd_args, capture_output=True, cwd=t, input=b"# stdin\n")
                if (py.returncode, py.stdout, py.stderr) != (rs.returncode, rs.stdout, rs.stderr):
                    bad += 1
                    print(f"MISMATCH file {name!r}\n  python={py!r}\n  rust  ={rs!r}")
        # UTF-8 이 아닌 파일 이름(바이트)
        weird = os.fsencode(str(t)) + b"/weird\xff\xe2\x82.md"
        os.chdir(t)
        for cmd_args in ([weird], [weird, "--json"]):
            total += 1
            py = subprocess.run(PY + cmd_args, capture_output=True, cwd=t)
            rs = subprocess.run(RS + cmd_args, capture_output=True, cwd=t)
            if (py.returncode, py.stdout, py.stderr) != (rs.returncode, rs.stdout, rs.stderr):
                bad += 1
                print(f"MISMATCH weird name\n  python={py!r}\n  rust  ={rs!r}")
        os.chdir(ROOT)
        (t / "locked.md").chmod(0o600)
        if os.geteuid() == 0:
            print("note: root 라서 읽기 권한 시험은 의미가 없다")

    print(f"edge_docs: {total - bad}/{total} match")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
