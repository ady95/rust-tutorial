"""스윕이 실제로 정상 출력을 비교했는지 확인 (종료 코드·출력 크기)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from x_lib import ROOT, both  # noqa: E402

d = os.path.join(ROOT, "verify", "x_work_text")
for name in ("single", "sig_ign", "infix"):
    p = os.fsencode(os.path.join(d, name + ".txt"))
    py, rs = both([p, b"--top", b"9" * 30, b"--json"], cwd=ROOT)
    print(name, "py", py[0], len(py[1]), py[1][:80], "rs", rs[0], len(rs[1]), py[1] == rs[1])
