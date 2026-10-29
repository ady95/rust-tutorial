"""독립 검증용 공통 도구 (x_ 접두사 파일은 검증 단계가 새로 만든 것)."""
from __future__ import annotations

import os
import subprocess
from concurrent.futures import ThreadPoolExecutor

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY = os.path.join(ROOT, ".venv", "bin", "python")
REF = os.path.join(ROOT, "python_src", "wordfreq.py")
RS = os.path.join(ROOT, "rust_app", "target", "release", "wordfreq")
WORK = os.path.join(ROOT, "verify", "x_work")

ENV = {k: v for k, v in os.environ.items() if k not in ("COLUMNS", "LINES")}


def _run(cmd, cwd, stdin=None, env=None, **kw):
    p = subprocess.run(cmd, cwd=cwd, capture_output=True, timeout=120,
                       stdin=stdin if stdin is not None else subprocess.DEVNULL,
                       env=env or ENV, **kw)
    return (p.returncode, p.stdout, p.stderr)


def run_py(args: list[bytes], cwd=WORK, **kw):
    return _run([os.fsencode(PY), os.fsencode(REF), *args], cwd, **kw)


def run_rs(args: list[bytes], cwd=WORK, **kw):
    return _run([os.fsencode(RS), *args], cwd, **kw)


def both(args, cwd=WORK, **kw):
    return run_py(args, cwd, **kw), run_rs(args, cwd, **kw)


def judge(py, rs):
    """계약 기준 비교. 같으면 None, 다르면 사유 문자열."""
    if py[0] == 2 and rs[0] == 2:
        return None if rs[2] else "rust usage error with empty stderr"
    if py[0] != rs[0]:
        return f"exit py={py[0]} rs={rs[0]}"
    if py[1] != rs[1]:
        return "stdout differs"
    if py[2] != rs[2]:
        return "stderr differs"
    return None


def parallel(fn, items, workers=8):
    with ThreadPoolExecutor(workers) as ex:
        return list(ex.map(fn, items))
