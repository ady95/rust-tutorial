"""stats 의 Python 기준 구현과 Rust 구현을 무작위 입력으로 비교하고, 비교 규칙별 불일치 수를 센다 (07-4).

입력 종류(각 --n 개, 고정 seed):
  plain     : -1000~1000 사이 소수 둘째 자리 숫자 2~30개
  halfway   : 평균이 x.xx5 근처가 되도록 만든 입력(반올림 경계)
  magnitude : 1e15~1e20, 1e-7~1e-4 처럼 문자열 표현이 바뀌는 크기
  cancel    : 1e16, 1, -1e16 처럼 더하는 순서에 따라 합이 달라지는 입력

비교 규칙:
  exact   : stdout·stderr·종료 코드 바이트 일치
  numeric : 줄마다 "이름: 값" 으로 나눠 값을 float 으로 읽은 뒤 비교.
            count 는 같아야 하고, 나머지는 상대 오차 1e-9 또는 절대 오차 1e-12 이내면 같다고 본다

사용법: python3 evaluate.py <Rust 실행 파일> [--n 500]
"""

import argparse
import json
import math
import random
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REFERENCE = HERE / "task" / "python_src" / "stats.py"


def gen_plain(rng: random.Random) -> list[str]:
    return [f"{rng.randint(-100000, 100000) / 100}" for _ in range(rng.randint(2, 30))]


def gen_halfway(rng: random.Random) -> list[str]:
    # 두 수의 평균이 정확히 xx.xx5 가 되게: a + b = 2 * (k + 0.005)
    k = rng.randint(0, 99999) / 100
    a = rng.randint(0, 9999) / 1000
    return [repr(a), repr(round(2 * (k + 0.005) - a, 6))]


def gen_magnitude(rng: random.Random) -> list[str]:
    big = [repr(rng.uniform(1e15, 1e20)) for _ in range(rng.randint(1, 3))]
    small = [repr(rng.uniform(1e-7, 1e-4)) for _ in range(rng.randint(1, 3))]
    return big + small


def gen_cancel(rng: random.Random) -> list[str]:
    big = rng.choice([1e16, 1e17, 2.0**53])
    small = [repr(rng.uniform(0.1, 10.0)) for _ in range(rng.randint(1, 4))]
    return [repr(big)] + small + [repr(-big)]


GENERATORS = {"plain": gen_plain, "halfway": gen_halfway, "magnitude": gen_magnitude, "cancel": gen_cancel}


def run(cmd: list[str]) -> tuple[int, str, str]:
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    return proc.returncode, proc.stdout, proc.stderr


def fields(out: str) -> dict[str, str]:
    return dict(line.split(": ", 1) for line in out.splitlines() if ": " in line)


def numeric_same(py: tuple[int, str, str], rs: tuple[int, str, str]) -> tuple[bool, list[str]]:
    if py[0] != rs[0] or py[2] != rs[2]:
        return False, ["exit/stderr"]
    a, b = fields(py[1]), fields(rs[1])
    if a.keys() != b.keys():
        return False, ["keys"]
    bad = []
    for key in a:
        if key == "count":
            if a[key] != b[key]:
                bad.append(key)
            continue
        x, y = float(a[key]), float(b[key])
        if not math.isclose(x, y, rel_tol=1e-9, abs_tol=1e-12):
            bad.append(key)
    return not bad, bad


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("rust", type=Path)
    parser.add_argument("--n", type=int, default=500)
    parser.add_argument("--seed", type=int, default=7)
    args = parser.parse_args()
    rng = random.Random(args.seed)
    summary = {}
    examples = {}
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "in.txt"
        for name, gen in GENERATORS.items():
            exact_diff = numeric_diff = 0
            text_only = {}
            value_fields = {}
            for _ in range(args.n):
                path.write_text("\n".join(gen(rng)) + "\n", encoding="utf-8")
                py = run([sys.executable, str(REFERENCE), str(path)])
                rs = run([str(args.rust.resolve()), str(path)])
                if py == rs:
                    continue
                exact_diff += 1
                ok, bad = numeric_same(py, rs)
                if ok:
                    # 값은 같은데 글자가 다른 필드
                    a, b = fields(py[1]), fields(rs[1])
                    for key in a:
                        if a[key] != b.get(key):
                            text_only[key] = text_only.get(key, 0) + 1
                            examples.setdefault(f"{name}/{key}/text", (a[key], b.get(key)))
                else:
                    numeric_diff += 1
                    for key in bad:
                        value_fields[key] = value_fields.get(key, 0) + 1
                        a, b = fields(py[1]), fields(rs[1])
                        examples.setdefault(f"{name}/{key}/value", (a.get(key), b.get(key), path.read_text()))
            summary[name] = {"n": args.n, "exact_diff": exact_diff, "numeric_diff": numeric_diff,
                             "text_only_fields": text_only, "value_diff_fields": value_fields}
            print(json.dumps({name: summary[name]}, ensure_ascii=False))
    print(json.dumps({"examples": examples}, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
