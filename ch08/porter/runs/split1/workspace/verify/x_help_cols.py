"""R4: 도움말 출력이 COLUMNS 환경 변수에 따라 Python 과 달라지는지."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from x_lib import ENV, ROOT, judge, run_py, run_rs  # noqa: E402

for cols in (None, "41", "42", "43", "44", "45", "46", "47", "48", "49", "50"):
    env = dict(ENV)
    if cols is not None:
        env["COLUMNS"] = cols
    py = run_py([b"-h"], cwd=ROOT, env=env)
    rs = run_rs([b"-h"], cwd=ROOT, env=env)
    print("COLUMNS", cols, "py", py[0], "rs", rs[0], "->", judge(py, rs) or "same")
    if judge(py, rs):
        print("   py", py[1])
        print("   rs", rs[1])
