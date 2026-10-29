"""문자열→정수 lax 변환의 모형(Rust lax::str_as_int 와 같은 규칙)을 pydantic 실측과 무작위로 비교한다.

사용법: uv run python verify/int_model.py [반복 수]
"""

from __future__ import annotations

import random
import re
import sys

from probe_lax import INT, run

# Rust str::trim 이 지우는 문자(Unicode White_Space)
WHITE_SPACE = "\t\n\x0b\x0c\r \x85\xa0 " + "".join(chr(c) for c in range(0x2000, 0x200B)) + "    　"
UNDERSCORE_OK = re.compile(r"[+-]?[0-9]+(?:_[0-9]+)*(?:\.[0-9]+(?:_[0-9]+)*)?", re.ASCII)
DIGITS = re.compile(r"-?[0-9_]+", re.ASCII)
LIMIT = 4300


def json_int(t: str) -> str | int | None:
    """JSON 정수 문법 -?(0|[1-9][0-9]*) 으로 앞에서부터 읽는다. '-' 포함 4300자를 넘으면 크기 오류."""
    i = 1 if t.startswith("-") else 0
    if i < len(t) and t[i] == "0":
        i += 1
    elif i < len(t) and t[i] in "123456789":
        while i < len(t) and t[i] in "0123456789":
            i += 1
            if i > LIMIT:
                return "int_parsing_size"
    else:
        return None
    return int(t) if i == len(t) else None


def signed_zeros(u: str) -> int | None:
    """부호 하나 → 앞의 0 → JSON 정수. 0을 떼지 않았으면 부호 없는 정수만 받는다."""
    prefix = ""
    if u.startswith("-"):
        prefix, u = "-", u[1:]
    elif u.startswith("+"):
        u = u[1:]
    if u.startswith("0"):
        if u.endswith("_"):
            return None
        u = u.lstrip("0_")
        if not u:
            return 0
    elif u.startswith("-"):
        return None
    if "_" in u:
        if u.startswith("_") or u.endswith("_") or "__" in u:
            return None
        u = u.replace("_", "")
    r = json_int(prefix + u)
    return r if isinstance(r, int) else None


def model(s: str) -> str | int:
    r = json_int(s)
    if r is not None:
        return r
    u = s.strip(WHITE_SPACE)
    candidates = [u]
    m = re.fullmatch(r"(.*)\.0+", u, re.DOTALL)
    if m:
        candidates.append(m[1])
    for cand in candidates:
        r = signed_zeros(cand)
        if r is not None:
            return r
    return "int_parsing"


def actual(s: str) -> str | int:
    out = run(INT, s)
    if out.startswith("OK "):
        return int(out[3:])
    return out[4:]


TOKENS = ["0", "1", "9", "_", "-", "+", ".", " ", "x", "٥", "00", "　", "\x1c", "5"]


def sample(rng: random.Random) -> str:
    kind = rng.random()
    small = "".join(rng.choice(TOKENS) for _ in range(rng.randint(0, 7)))
    if kind < 0.7:
        return small
    run_len = rng.randint(4295, 4305)
    digit = rng.choice("019")
    pre = "".join(rng.choice(TOKENS) for _ in range(rng.randint(0, 3)))
    post = "".join(rng.choice(TOKENS) for _ in range(rng.randint(0, 3)))
    return pre + digit * run_len + post


def main() -> int:
    sys.set_int_max_str_digits(0)
    count = int(sys.argv[1]) if len(sys.argv) > 1 else 20000
    rng = random.Random(1)
    bad = 0
    for _ in range(count):
        s = sample(rng)
        want, got = actual(s), model(s)
        if want != got:
            bad += 1
            if bad <= 15:
                print(f"DIFF {s[:20]!r}...{s[-12:]!r} len={len(s)} pydantic={str(want)[:20]} model={str(got)[:20]}")
    print(f"{count - bad}/{count} match")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
