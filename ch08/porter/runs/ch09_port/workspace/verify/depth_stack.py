"""기준 구현에서 JSON 중첩 한도가 호출 맥락에 따라 달라지는지 잰다(계약은 9997).

맥락: 최상위, Python 재귀 900단계 안, 스레드 안, C 콜백(sorted key / map) 안, Hypothesis @given 안(fuzz 와 같은 경로),
그리고 python_src/logstat.py 를 하위 프로세스로 실행(main 경로).
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
import threading
from pathlib import Path

from hypothesis import given, settings, strategies as st

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "python_src"))
import logstat  # noqa: E402


def ok_at(depth: int) -> bool:
    line = '{"a":' * depth + "1" + "}" * depth
    code, _, err = logstat.run(line + "\n", "jsonl", 10, False, True)
    return "invalid json" not in err


def limit() -> int:
    lo, hi = 1, 20000  # ok_at(lo) 참, ok_at(hi) 거짓
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if ok_at(mid):
            lo = mid
        else:
            hi = mid
    return lo


def nested(n: int) -> int:
    return limit() if n == 0 else nested(n - 1)


results: dict[str, int] = {"top level": limit(), "python recursion 900": nested(900)}
box: list[int] = []
t = threading.Thread(target=lambda: box.append(limit()))
t.start()
t.join()
results["thread"] = box[0]
results["list comprehension"] = [limit() for _ in [0]][0]
results["map() callback (C)"] = list(map(lambda _: limit(), [0]))[0]
key_out: list[int] = []
sorted([0], key=lambda _: key_out.append(limit()) or 0)
results["sorted(key=) callback (C)"] = key_out[0]

seen: list[int] = []


@settings(max_examples=1, deadline=None, database=None)
@given(st.just(0))
def under_hypothesis(_: int) -> None:
    seen.append(limit())


under_hypothesis()
results["hypothesis @given (fuzz 경로)"] = seen[0]

tmp = Path(tempfile.mkdtemp())
for depth in (9997, 9998):
    p = tmp / f"d{depth}.jsonl"
    p.write_text('{"a":' * depth + "1" + "}" * depth + "\n")
    r = subprocess.run([sys.executable, str(ROOT / "python_src" / "logstat.py"), str(p), "--strict"],
                       capture_output=True, text=True)
    results[f"main subprocess depth {depth}"] = r.stderr.strip()

for k, v in results.items():
    print(f"{k}: {v}")
