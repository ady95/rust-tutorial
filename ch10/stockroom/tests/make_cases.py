"""tests/cases.json 을 만든다. 케이스마다 서버 상태를 비운 뒤 steps 의 요청을 차례로 보낸다(automation/compare.py)."""

from __future__ import annotations

import base64
import json
from pathlib import Path

JSON = {"Content-Type": "application/json"}


def item(name: str = "bolt", price: object = 1.5, quantity: object = 10, **extra: object) -> dict:
    return {"name": name, "price": price, "quantity": quantity} | extra


def post(body: object) -> dict:
    return {"method": "POST", "path": "/items", "json": body}


def raw(method: str, path: str, text: str, headers: dict | None = None) -> dict:
    return {"method": method, "path": path, "body": text, "headers": JSON if headers is None else headers}


def get(path: str) -> dict:
    return {"method": "GET", "path": path}


SEED = [post(item("bolt", 0.00001, 5, tags=["hw"])), post(item("nut", 10, "7", tags=["hw", "small"])),
        post(item("gear", 999999.9999999999, 1))]

CASES = {
    "health": [get("/health")],
    "create-get-list": [*SEED, get("/items/1"), get("/items"), get("/items?limit=2&offset=1"), get("/items?tag=hw")],
    "float-format": [post(item("f", p, 1)) for p in (10, 1e-7, 0.1, 5e-324, 123456.789, "1e-5")],
    "lax-numbers": [post(item("l", "12.5", "3")), post(item("l", True, True)), post(item("l", " 2 ", 3.0)),
                    post(item("l", "1_0.5", "1_0")), post(item("l", 1, False))],
    "validation-types": [post(item(quantity=3.5)), post(item(quantity=None)), post(item(price=None)),
                         post(item(price="true")), post(item(name=5)), post(item(tags="abc")), post(item(tags=[1]))],
    "validation-ranges": [post(item(name="", price=-1, extra=1)), post(item(name="x" * 101)), post(item(tags=["a"] * 11)),
                          post(item(tags=[""])), post(item(quantity=1_000_001)), post(item(price="inf"))],
    "unicode-name": [post(item("\U0001F600" * 100)), post(item("\U0001F600" * 101)), post(item("값 x"))],
    "missing-fields": [post({"name": "x"}), post({}), post({"price": 1, "quantity": 1, "tags": []})],
    "non-finite-body": [raw("POST", "/items", '{"name":"p","price":NaN,"quantity":1}'),
                        raw("POST", "/items", '{"name":"p","price":Infinity,"quantity":1}'),
                        raw("POST", "/items", '{"name":"p","price":1e400,"quantity":1}')],
    "body-framing": [raw("POST", "/items", '{"name":"t","price":1,"quantity":1}', {}),
                     raw("POST", "/items", '{"name":"t","price":1,"quantity":1}', {"Content-Type": "application/vnd.api+json"}),
                     raw("POST", "/items", '{"name":"t","price":1,"quantity":1}', {"Content-Type": "application/json; charset=utf-8"}),
                     raw("POST", "/items", '{"name":"t","price":1,"quantity":1}', {"Content-Type": "text/plain"}),
                     raw("POST", "/items", ""), raw("POST", "/items", "null"), raw("POST", "/items", "[1]")],
    "invalid-json": [raw("POST", "/items", "{bad"), raw("POST", "/items", '{"name":"t","price":1,"quantity":1} x'),
                     raw("POST", "/items", '{"name":"é", "price": 1,'), raw("POST", "/items", '{"name":"t","name":"u","price":1,"quantity":1}')],
    "invalid-utf8": [{"method": "POST", "path": "/items", "headers": JSON,
                      "body_b64": base64.b64encode(b'{"name":"\xe9","price":1,"quantity":1}').decode()}],
    "path-ints": [*SEED[:1], *[get(f"/items/{s}") for s in ("01", "+1", "%201", "1.0", "1_0", "1e0", "0x1", "-0", "-1",
                                                           "99999999999999999999", "%D9%A1", "abc")]],
    "query-ints": [*SEED, *[get(f"/items?{q}") for q in ("limit=0&offset=-1", "limit=101", "limit=5.0", "limit=5.5",
                                                         "limit=%205%20", "limit=", "limit=1&limit=2", "tag=", "tag=x&tag=hw")]],
    "routing": [get("/Items"), get("/nope"), get("/items//1"), get("/items/"), get("/items/?limit=1"),
                {"method": "POST", "path": "/items/", "json": item()}, get("/stats/"), get("/items/1/reserve/"), get("/nope/")],
    "method-not-allowed": [{"method": m, "path": p} for m, p in [("PUT", "/items"), ("PUT", "/items/1"), ("GET", "/items/1/reserve"),
                                                                 ("POST", "/stats"), ("DELETE", "/health"), ("HEAD", "/items"),
                                                                 ("OPTIONS", "/health"), ("GET", "/_test/reset")]],
    "patch": [*SEED, {"method": "PATCH", "path": "/items/1", "json": {}}, {"method": "PATCH", "path": "/items/1", "json": {"name": None}},
              {"method": "PATCH", "path": "/items/1", "json": {"price": "2.5", "tags": ["a", "b"]}},
              {"method": "PATCH", "path": "/items/99", "json": {"bogus": 1}}, {"method": "PATCH", "path": "/items/99", "json": {}},
              get("/items/1")],
    "delete": [*SEED, {"method": "DELETE", "path": "/items/2"}, {"method": "DELETE", "path": "/items/2"}, get("/items"),
               post(item("after")), get("/items/4")],
    "reserve": [*SEED, {"method": "POST", "path": "/items/1/reserve", "json": {"quantity": 10}},
                {"method": "POST", "path": "/items/1/reserve", "json": {"quantity": 2}},
                {"method": "POST", "path": "/items/1/reserve", "json": {"quantity": 3}},
                {"method": "POST", "path": "/items/1/reserve", "json": {"quantity": 1}},
                {"method": "POST", "path": "/items/1/reserve", "json": {"quantity": 0}},
                {"method": "POST", "path": "/items/1/reserve", "json": {}},
                {"method": "POST", "path": "/items/abc/reserve", "json": {"quantity": 0}},
                {"method": "POST", "path": "/items/9/reserve", "json": {"quantity": 1}}, get("/items/1")],
    "stats": [get("/stats"), *[post(item("s", p, 3)) for p in (0.1, 0.2, 0.3)], get("/stats"),
              post(item("big", 1_000_000, 1_000_000)), get("/stats")],
}


def main() -> None:
    cases = [{"name": name, "steps": steps} for name, steps in CASES.items()]
    path = Path(__file__).resolve().parent / "cases.json"
    path.write_text(json.dumps(cases, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(f"{len(cases)} cases, {sum(len(c['steps']) for c in cases)} requests")


if __name__ == "__main__":
    main()
