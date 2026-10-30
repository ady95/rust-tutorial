"""automation/port.json 의 bench 사례를 Python 과 Rust 로 돌려 출력이 같은지 확인한다 (인자: 생성된 bench 폴더)."""

import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PY = [sys.executable, str(ROOT / "python_src" / "mdtoc.py")]
BIN = [str(ROOT / "rust_app" / "target" / "release" / "mdtoc")]


def main(bench_dir):
    cases = {"large-doc": [f"{bench_dir}/large.md"], "large-doc-json": [f"{bench_dir}/large.md", "--json"],
             "small-doc": ["tests/fixtures/basic.md"]}
    bad = 0
    for name, args in cases.items():
        t0 = time.perf_counter()
        py = subprocess.run([*PY, *args], capture_output=True, cwd=ROOT)
        t1 = time.perf_counter()
        rs = subprocess.run([*BIN, *args], capture_output=True, cwd=ROOT)
        t2 = time.perf_counter()
        same = (py.returncode, py.stdout, py.stderr) == (rs.returncode, rs.stdout, rs.stderr)
        bad += not same
        print(f"{name:15} same={same} bytes={len(py.stdout)} python={t1 - t0:.3f}s rust={t2 - t1:.3f}s")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
