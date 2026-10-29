"""COLUMNS 값에 따라 기준 구현의 도움말이 몇 가지로 달라지는지 본다."""

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
outputs: dict[bytes, list[str]] = {}
for cols in ["", "0", "-5", "abc"] + [str(c) for c in range(1, 201)] + ["1000"]:
    env = {k: v for k, v in os.environ.items() if k not in ("COLUMNS", "LINES")}
    if cols:
        env["COLUMNS"] = cols
    p = subprocess.run([sys.executable, str(ROOT / "python_src" / "logstat.py"), "-h"], capture_output=True, env=env)
    outputs.setdefault(p.stdout, []).append(cols or "unset")
for out, cols in outputs.items():
    print(cols[0], "..", cols[-1], len(cols))
print(len(outputs), "distinct outputs")
