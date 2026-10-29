"""무작위 요청열로 기준 구현 서버와 Rust 서버를 비교한다 (Hypothesis).

요청열마다 두 서버의 상태를 비우고, 생성·조회·수정·삭제·예약·목록·통계와 잘못된 경로·메서드·본문을 섞어 보낸다.
실패하면 Hypothesis 가 줄인 가장 짧은 요청열을 보여 준다. seed 를 주지 않으면 실행할 때마다 다른 입력을 만든다.

사용법 (프로젝트 루트에서): uv run python automation/fuzz.py [--rust BIN] [--examples 300] [--seed N]
종료 코드: 0 = 차이 없음, 1 = 차이 발견, 2 = Rust 실행 파일 없음, 3 = 서버를 띄우지 못함
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from urllib.parse import quote

from hypothesis import HealthCheck, given, seed, settings
from hypothesis import strategies as st

sys.path.insert(0, str(Path(__file__).resolve().parent))

from http_diff import ROOT, run_steps, start_pair  # noqa: E402

int_text = st.one_of(st.integers(-3, 8).map(str), st.sampled_from(["01", "+1", " 2", "1.0", "1_0", "1e0", "", "x", "-0",
                                                                   "99999999999999999999", "١", "2.5", "true"]))
number = st.one_of(st.integers(-2, 1_000_001), st.floats(allow_nan=False, allow_infinity=False, width=64),
                   st.sampled_from([0.1, 1e-7, 0.00001, 5e-324, 999999.9999999999, 1e6, 1e6 + 1]), st.booleans(), st.none(),
                   int_text, st.sampled_from(["12.5", " 3 ", "1e-5", "inf", "nan", "1_0.5", "0x1p3"]))
name = st.one_of(st.text(min_size=0, max_size=6), st.just("x" * 101), st.integers(0, 9))
tags = st.one_of(st.lists(st.text(max_size=4), max_size=3), st.just("abc"), st.lists(st.integers(0, 3), max_size=2),
                 st.just(["t"] * 11))
fields = st.fixed_dictionaries({}, optional={"name": name, "price": number, "quantity": number, "tags": tags,
                                             "extra": st.integers(0, 1)})
good_item = st.fixed_dictionaries({"name": st.sampled_from(["a", "b", "값"]), "price": st.sampled_from([0.1, 0.2, 1.5, 10, 0.00001]),
                                   "quantity": st.integers(0, 6), "tags": st.lists(st.sampled_from(["x", "y"]), max_size=2,
                                                                                   unique=True)})
item_id = st.one_of(st.integers(0, 5).map(str), int_text.map(lambda s: quote(s, safe="")))
raw_body = st.sampled_from(['{"name":"p","price":NaN,"quantity":1}', "{bad", "null", "[1]", "",
                            '{"name":"t","name":"u","price":1,"quantity":1}', '{"name":"é", "price": 1,'])
content_type = st.sampled_from(["application/json", "application/vnd.api+json", "text/plain", None])

step = st.one_of(
    good_item.map(lambda b: {"method": "POST", "path": "/items", "json": b}),
    good_item.map(lambda b: {"method": "POST", "path": "/items", "json": b}),
    fields.map(lambda b: {"method": "POST", "path": "/items", "json": b}),
    st.builds(lambda i: {"method": "GET", "path": f"/items/{i}"}, item_id),
    st.builds(lambda i, b: {"method": "PATCH", "path": f"/items/{i}", "json": b}, item_id,
              st.one_of(fields, st.just({"name": None}))),
    st.builds(lambda i: {"method": "DELETE", "path": f"/items/{i}"}, item_id),
    st.builds(lambda i, q: {"method": "POST", "path": f"/items/{i}/reserve", "json": {"quantity": q}}, item_id,
              st.one_of(st.integers(-1, 7), number)),
    st.builds(lambda l, o, t: {"method": "GET", "path": "/items?" + "&".join(p for p in (l, o, t) if p)},
              st.one_of(st.none(), int_text.map(lambda s: "limit=" + quote(s, safe=""))),
              st.one_of(st.none(), int_text.map(lambda s: "offset=" + quote(s, safe=""))),
              st.one_of(st.none(), st.sampled_from(["tag=x", "tag=y", "tag=", "tag=x&tag=y"]))),
    st.just({"method": "GET", "path": "/stats"}),
    st.builds(lambda b, ct: {"method": "POST", "path": "/items", "body": b, "headers": {"Content-Type": ct} if ct else {}},
              raw_body, content_type),
    st.sampled_from([{"method": m, "path": p} for m, p in [("PUT", "/items/1"), ("HEAD", "/items"), ("GET", "/items/"),
                                                         ("GET", "/stats/"), ("GET", "/nope"), ("GET", "/Items"),
                                                         ("OPTIONS", "/health"), ("GET", "/items/1/reserve")]]),
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Random request sequences against both servers.")
    parser.add_argument("--rust", type=Path, default=ROOT / "rust_app" / "target" / "release" / "stockroom")
    parser.add_argument("--examples", type=int, default=300)
    parser.add_argument("--seed", type=int)
    args = parser.parse_args()
    if not args.rust.exists():
        print(f"Rust binary not found: {args.rust}", file=sys.stderr)
        return 2
    try:
        python, rust = start_pair(args.rust)
    except RuntimeError as err:
        print(f"ERROR {err}", file=sys.stderr)
        return 3
    failure: dict[str, object] = {}

    @settings(max_examples=args.examples, deadline=None, database=None,
              suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large])
    @given(steps=st.lists(step, min_size=1, max_size=12))
    def check(steps: list[dict]) -> None:
        problems = run_steps(python, rust, steps)
        if problems:
            failure.update(steps=steps, problems=problems)
        assert not problems

    if args.seed is not None:
        check = seed(args.seed)(check)
    try:
        check()
    except AssertionError:
        print("FAIL random request sequence differs")
        for index, s in enumerate(failure["steps"], 1):
            print(f"     {index}. {str(s)[:300]}")
        for problem in failure["problems"]:
            print(f"     {problem}")
        return 1
    finally:
        python.stop()
        rust.stop()
    print(f"OK   {args.examples} random request sequences match")
    return 0


if __name__ == "__main__":
    sys.exit(main())
