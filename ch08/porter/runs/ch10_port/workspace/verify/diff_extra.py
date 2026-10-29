"""비교 도구가 다루지 않는 입력(port/plan.json 위험 항목의 '추가할 것')을 두 서버에 보내 비교한다.

사용법: uv run python verify/diff_extra.py [--rust rust_app/target/release/stockroom]
"""

from __future__ import annotations

import argparse
import base64
import json
import random
import sys
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "automation"))

from http_diff import run_steps, start_pair  # noqa: E402

JSON = {"Content-Type": "application/json"}


def raw(method: str, path: str, data: bytes, headers: dict | None = None) -> dict:
    return {"method": method, "path": path, "body_b64": base64.b64encode(data).decode(),
            "headers": JSON if headers is None else headers}


def post(body: object, path: str = "/items") -> dict:
    return {"method": "POST", "path": path, "json": body}


def get(path: str, headers: dict | None = None) -> dict:
    return {"method": "GET", "path": path, "headers": headers or {}}


def item(**fields: object) -> dict:
    return {"name": "n", "price": 1.5, "quantity": 3} | fields


SEED = [post(item(tags=["x"])), post(item(name="b", price=0.1, quantity=7))]

JSON_DOCS = ['{"a" 1}', '{"a":1,}', '[1,]', '{', '"\x01"', '"\\q"', '"\\u12"', '"abc', '-', '01', '1.', 'tru', ' ',
             '"\\ud800\\u12"', '"\\ud800\\uzzzz"', '[1 2]', '{"a":}', '{"a":1 "b"}', '[', '"\\', '"\\u1234', 'nul',
             'NaN1', '-Infinit', '1e+', '1.e5', '-a', '{}{}', '{"\\ud800":1', '{"é" 1}', '"😀" x', ' \t\n\r{',
             '{"name":"a","price":1,"quantity":1}\n', '{"name":"a","price":1e999,"quantity":1}']
BODIES = [b'\xef\xbb\xbf{"name":"a","price":1,"quantity":1}', '{"name":"a","price":1,"quantity":1}'.encode("utf-16"),
          '{"name":"a","price":1,"quantity":1}'.encode("utf-16-le"), '{"name":"a","price":1,"quantity":1}'.encode("utf-32"),
          '{"name":"a","price":1,"quantity":1}'.encode("utf-16-be"), '{"name":"a","price":1,"quantity":1}'.encode("utf-32-le"),
          b'{"name":"\xed\xa0\x80","price":1,"quantity":1}', b'{"name":"\xe9', b'\xef\xbb\xbf', b'\xff\xfe', b'{\x00',
          b'{"name":"a","price":1,"quantity":' + b"1" * 4301 + b"}", b'{"name":"a","price":1,"quantity":' + b"1" * 4300 + b"}",
          b'{"name":"a","price":' + b"1" * 400 + b',"quantity":1}', b'{"name":"\\ud800","price":1,"quantity":1}',
          b'{"name":"a","price":1,"quantity":1,"\\udc00":1}', b'{"name":"a","price":1,"quantity":1,"tags":["\\ud800"]}',
          b'{"name":"a","price":"\\ud800","quantity":"\\ud800"}', '{"name":"a\\u0001b\x7f/ ","price":1,"quantity":1}'.encode()]
NAMES = ["a\u0001b", "a\u007fb", "a/b", "a b", "\t", "é", "\U0001F600" * 3, "\\", '"']
PRICES = [1e-6, 0.000123, 1e15, 1e16, 123456789012.5, -0.0, 1e-7, 5e-324, 2.5e-5, 999999.99, 1e6, 0.1 + 0.2, 1 / 3,
          "1__0", "_1", "1_", "1_e5", "Infinity", "-inf", "NAN", "+1.5", ".5", "5.", "1e", "١.5", "-0", 10**400,
          -0, 0, "-0.0", True, False, [], {}, " 1", " 1_0"]
QTYS = [1e3, 99999999999999999999, -0.0, 3.0, 3.5, 1e30, "1_0", "1e3", " 3", "3.0", "+3", "　" + "3", True, None,
        float("nan"), 2.0**63, -(2.0**63), "0-1", "+00-9"]
CONTENT_TYPES = ["APPLICATION/JSON", "application/jsonx", "application/json/x", "application/+json", "application/json ;x",
                 "", "json", "application/problem+json", "\x1capplication/json", "text/json", "application/JSON;"]
PATHS = ["/%69tems", "/health%0A", "/items%0A", "/items/1%0A", "/items/%FF", "/items/%2F", "/items//", "/items/abc/",
         "/items/%C3%A9/", "/items/%2541/", "/items/?a=%20b&c=%22", "//", "/", "/items/%ED%A0%80/", "/items/1%2Freserve",
         "/items/%3F/", "/items/a%23b/", "/items/a%5Cb/", "/health/?x", "/stats//?q=1", "/items/1/reserve%0A",
         "/items/%E3%80%801", "/items/%C2%A01", "/items/%1C1", "/items/5.", "/items/5.000", "/items/.0", "/items/_1",
         "/items/1_", "/items/1__0", "/items/-01", "/items/" + "0" * 30 + "1", "/items/" + "1" * 4301,
         "/items/%2B" + "1" * 4301, "/items/0-1", "/items/+00-2", "/items/{1}", "/items/a|b", "/_test/reset/",
         "/openapi.json/", "/items/1?x#y"]
QUERIES = ["limit=+5", "limit", "limit=5;offset=1", "tag=a+b", "tag=%E2%82%AC", "tag=%ZZ", "&&limit=2", "limit=5&offset=1",
           "offset=99999999999999999999", "offset=1e1", "limit=%2B1", "limit=0&offset=-1&limit=200", "tag=x&tag",
           "limit=1_0", "offset=-0", "tag=%FF", "limit=" + "1" * 4301]
HOSTS = ["example.com", "example.com:8080", "[::1]:99", "[::1", "a b", "EXAMPLE.com:099999", "x:65536", "[v1.x]",
         "[zz::1]", "hést", "user@host", "x:"]


def cases() -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    out["json-errors"] = [raw("POST", "/items", d.encode()) for d in JSON_DOCS]
    out["encodings"] = [raw("POST", "/items", b) for b in BODIES] + [get("/items")]
    out["names"] = [post(item(name=n)) for n in NAMES] + [post(item(tags=[n])) for n in NAMES] + [get("/items")]
    out["prices"] = [post(item(price=p)) for p in PRICES] + [get("/items?limit=100"), get("/stats")]
    out["quantities"] = [post(item(quantity=q)) for q in QTYS] + [get("/stats")]
    out["reserve-q"] = [*SEED] + [post({"quantity": q}, "/items/2/reserve") for q in QTYS] + [get("/items/2")]
    out["content-types"] = [raw("POST", "/items", b'{"name":"a","price":1,"quantity":1}', {"Content-Type": c})
                            for c in CONTENT_TYPES]
    out["paths"] = [*SEED] + [get(p) for p in PATHS] + [{"method": "POST", "path": p, "json": {}} for p in PATHS[:20]]
    out["queries"] = [*SEED] + [get("/items?" + q) for q in QUERIES]
    out["hosts"] = [get("/items/", {"Host": h}) for h in HOSTS]
    out["short-circuit"] = [*SEED, raw("POST", "/items/abc/reserve", b"{bad"), raw("PATCH", "/items/x", b"\xff"),
                            raw("POST", "/items/abc/reserve", b""), raw("GET", "/items/1", b"{bad"),
                            raw("PATCH", "/items/x?limit=0", b'{"name":5}'), raw("DELETE", "/items/1", b"\xff"),
                            raw("POST", "/items/abc/reserve", b'{"quantity":0,"x":1}')]
    out["tags"] = [post(item(tags=t)) for t in (["" for _ in range(11)], [1] * 11, [1, "", "x" * 21] + ["a"] * 7,
                                                ["a"] * 10, None, {"a": 1}, "abc", [None])]
    out["patch"] = [*SEED, {"method": "PATCH", "path": "/items/1", "json": {"price": 3, "tags": None}},
                    {"method": "PATCH", "path": "/items/1", "json": {"price": None, "bogus": 1}},
                    {"method": "PATCH", "path": "/items/1", "json": {"quantity": "7", "name": "z"}},
                    {"method": "PATCH", "path": "/items/01", "json": []}, get("/items/1")]
    out["stats-edge"] = [post(item(price=-0.0, quantity=3)), get("/stats"), post(item(price=1e-7, quantity=1)),
                         post(item(price=5e-324, quantity=1)), post(item(price=1e6, quantity=1_000_000)), get("/stats")]
    out["methods"] = [{"method": m, "path": p} for m in ("HEAD", "OPTIONS", "FOO", "PUT", "POST", "PATCH")
                      for p in ("/health", "/items/1", "/stats", "/items/1/reserve", "/_test/reset")]
    rng = random.Random(7)
    prices = ([rng.uniform(0, 1e6) for _ in range(100)] + [rng.random() * 10.0 ** rng.randint(-320, 5) for _ in range(500)]
              + [round(rng.random() * 10 ** rng.randint(0, 6), rng.randint(0, 8)) for _ in range(200)])
    out["random-prices"] = [post(item(price=p, quantity=rng.randint(0, 9))) for p in prices] + [get("/stats")]
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rust", type=Path, default=ROOT / "rust_app" / "target" / "release" / "stockroom")
    args = parser.parse_args()
    python, rust = start_pair(args.rust)
    failed = 0
    try:
        for name, steps in cases().items():
            # 케이스 안에서 처음 다른 응답에서 멈추므로 요청 하나씩 따로 비교한다(앞 단계는 상태 준비용)
            seeds = [s for s in steps if s in SEED]
            problems_all = []
            for step in steps:
                if step in SEED:
                    continue
                problems = run_steps(python, rust, [*seeds, step])
                if problems:
                    problems_all.append(problems)
            # 상태가 쌓이는 경우(stats 등)를 보려고 요청열 전체도 한 번 비교한다
            whole = run_steps(python, rust, steps)
            if whole and not problems_all:
                problems_all.append(["(whole sequence)", *whole])
            failed += bool(problems_all)
            print(f"{'OK  ' if not problems_all else 'FAIL'} {name} ({len(steps)} steps)")
            for problems in problems_all[:6]:
                for line in problems:
                    print(f"     {line[:300]}")
    finally:
        python.stop()
        rust.stop()
    return 1 if failed else 0


if __name__ == "__main__":
    json.dumps({})
    sys.exit(main())
