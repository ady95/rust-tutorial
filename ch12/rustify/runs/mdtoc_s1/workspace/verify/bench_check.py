"""automation/gen_bench.py 가 만든 큰 문서로 Python 과 Rust 의 출력을 비교하고 시간을 잰다.

    python3 verify/bench_check.py
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PY = [sys.executable, str(ROOT / "python_src" / "mdtoc.py")]
RS = [str(ROOT / "rust_app" / "target" / "release" / "mdtoc")]


def timed(cmd: list[str]) -> tuple[tuple[int, bytes, bytes], float]:
    start = time.perf_counter()
    proc = subprocess.run(cmd, capture_output=True, cwd=ROOT, timeout=600)
    return (proc.returncode, proc.stdout, proc.stderr), time.perf_counter() - start


def main() -> int:
    bad = 0
    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run([sys.executable, str(ROOT / "automation" / "gen_bench.py"), tmp], check=True, cwd=ROOT)
        large = str(Path(tmp) / "large.md")
        for name, args in (("large-doc", [large]), ("large-doc-json", [large, "--json"]),
                           ("small-doc", ["tests/fixtures/basic.md"])):
            py, py_t = timed(PY + args)
            rs, rs_t = timed(RS + args)
            ok = py == rs
            bad += not ok
            print(f"{'OK  ' if ok else 'FAIL'} {name}: python {py_t:.3f}s rust {rs_t:.3f}s ({len(rs[1])} bytes)")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
