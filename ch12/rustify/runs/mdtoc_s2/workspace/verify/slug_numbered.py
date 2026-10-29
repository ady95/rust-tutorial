"""2판 변경(앵커 겹침 방지, --numbered)을 기준 구현과 비교한다.

    python3 verify/slug_numbered.py
"""
import itertools
import random
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "python_src"))
RUST = ROOT / "rust_app" / "target" / "release" / "mdtoc"
PY = ROOT / "python_src" / "mdtoc.py"

TITLES = ["A", "a", "a-1", "a-2", "a-1-1", "A!", "!!", "", "b", "b-1", "x y", "x-y"]


def run(cmd: list[str], data: bytes) -> tuple[int, bytes, bool]:
    p = subprocess.run(cmd, input=data, capture_output=True)
    return p.returncode, p.stdout, bool(p.stderr)


def check(doc: str, extra: list[str]) -> int:
    data = doc.encode()
    py = run([sys.executable, str(PY), *extra], data)
    rs = run([str(RUST), *extra], data)
    if py != rs:
        print("MISMATCH", repr(doc), extra, py, rs)
        return 1
    return 0


def main() -> int:
    bad = 0
    count = 0
    flag_sets = [[], ["--json"], ["--numbered"], ["--numbered", "--min-level", "2"],
                 ["--numbered", "--json"], ["--min-level", "2", "--max-level", "3"]]
    # 제목 목록의 길이 3 이하 조합 전부(수준은 1~2 를 번갈아)
    for n in range(1, 4):
        for combo in itertools.product(TITLES, repeat=n):
            for levels in ((1,) * n, (1, 2, 3)[:n], (2, 1, 3)[:n]):
                doc = "".join(f"{'#' * lv} {t}\n" for lv, t in zip(levels, combo))
                bad += check(doc, ["--numbered"])
                count += 1
    # 무작위 긴 문서
    rng = random.Random(20261030)
    for _ in range(300):
        doc = "".join(
            f"{'#' * rng.randint(1, 6)} {rng.choice(TITLES)}\n" for _ in range(rng.randint(1, 25))
        )
        for flags in flag_sets:
            bad += check(doc, flags)
            count += 1
    print(f"{count} cases, {bad} mismatches")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
