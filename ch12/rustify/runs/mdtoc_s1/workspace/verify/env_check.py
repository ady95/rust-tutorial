"""확신하지 못했던 환경 의존 항목을 실제로 확인한다.

    python3 verify/env_check.py
    uv run python verify/env_check.py

출력: 실행 중인 Python 버전/unidata/경로, root 여부, 권한 없는 파일을 Python 과 Rust 가 어떻게 다루는지.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PY = [sys.executable, str(ROOT / "python_src" / "mdtoc.py")]
RS = [str(ROOT / "rust_app" / "target" / "release" / "mdtoc")]


def main() -> int:
    print(f"python {sys.version.split()[0]} at {sys.executable}, unidata {unicodedata.unidata_version}")
    print(f"euid {os.geteuid()}")
    table_head = (ROOT / "rust_app" / "src" / "unicode_tables.rs").read_text(encoding="utf-8").splitlines()[0]
    print(f"table header: {table_head}")
    with tempfile.TemporaryDirectory() as tmp:
        f = Path(tmp) / "locked.md"
        f.write_text("# x\n", encoding="utf-8")
        f.chmod(0)
        results = [subprocess.run(c + [str(f)], capture_output=True) for c in (PY, RS)]
        f.chmod(0o600)
    for name, r in zip(("python", "rust"), results):
        print(f"{name}: exit {r.returncode} stdout {r.stdout!r} stderr {r.stderr!r}")
    py, rs = results
    denied = py.returncode == 1
    print(f"permission path exercised: {denied}")
    same = (py.returncode, py.stdout, py.stderr.split(b": ", 2)[-1]) == (rs.returncode, rs.stdout, rs.stderr.split(b": ", 2)[-1])
    print("permission result same:", same)
    return 0 if same else 1


if __name__ == "__main__":
    sys.exit(main())
