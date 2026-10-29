import os

import pytest

os.environ["STOCKROOM_TEST"] = "1"

from fastapi.testclient import TestClient  # noqa: E402

from stockroom.app import app  # noqa: E402

client = TestClient(app)


@pytest.fixture(autouse=True)
def reset() -> None:
    assert client.post("/_test/reset").status_code == 204


def create(**fields: object) -> dict:
    body = {"name": "bolt", "price": 1.5, "quantity": 10} | fields
    response = client.post("/items", json=body)
    assert response.status_code == 201, response.text
    return response.json()


def errors(response) -> list[tuple[str, list]]:
    assert response.status_code == 422
    return [(e["type"], e["loc"]) for e in response.json()["detail"]]


def test_create_and_get() -> None:
    response = client.post("/items", json={"name": "bolt", "price": 0.00001, "quantity": 5, "tags": ["hw"]})
    assert response.status_code == 201
    assert response.headers["location"] == "/items/1"
    assert response.content == b'{"id":1,"name":"bolt","price":0.00001,"quantity":5,"tags":["hw"]}'
    assert client.get("/items/1").content == response.content


def test_float_format_follows_pydantic_core() -> None:
    for price, text in [(10, b"10.0"), (1e-7, b"1e-7"), (999999.9999999999, b"999999.9999999999")]:
        assert b'"price":' + text + b"," in client.post("/items", json={"name": "f", "price": price, "quantity": 1}).content


def test_lax_coercion() -> None:
    item = create(price="12.5", quantity="3")
    assert (item["price"], item["quantity"]) == (12.5, 3)
    assert create(quantity=True)["quantity"] == 1
    assert create(quantity=3.0)["quantity"] == 3
    assert create(quantity="1_0")["quantity"] == 10


@pytest.mark.parametrize(
    ("fields", "expected"),
    [
        ({"quantity": 3.5}, [("int_from_float", ["body", "quantity"])]),
        ({"quantity": None}, [("int_type", ["body", "quantity"])]),
        ({"price": None}, [("float_type", ["body", "price"])]),
        ({"price": "true"}, [("float_parsing", ["body", "price"])]),
        ({"name": 5}, [("string_type", ["body", "name"])]),
        ({"tags": "abc"}, [("list_type", ["body", "tags"])]),
        ({"tags": [""]}, [("string_too_short", ["body", "tags", 0])]),
        ({"tags": ["a"] * 11}, [("too_long", ["body", "tags"])]),
        ({"name": "", "price": -1, "extra": 1},
         [("string_too_short", ["body", "name"]), ("greater_than_equal", ["body", "price"]),
          ("extra_forbidden", ["body", "extra"])]),
    ],
)
def test_validation_errors(fields: dict, expected: list) -> None:
    body = {"name": "bolt", "price": 1.5, "quantity": 10} | fields
    assert errors(client.post("/items", json=body)) == expected


@pytest.mark.parametrize("raw", [b'{"name":"p","price":NaN,"quantity":1}', b'{"name":"p","price":Infinity,"quantity":1}'])
def test_non_finite_body_is_422_not_500(raw: bytes) -> None:
    response = client.post("/items", content=raw, headers={"content-type": "application/json"})
    assert errors(response) == [("less_than_equal", ["body", "price"])]


def test_body_framing() -> None:
    body = b'{"name":"t","price":1,"quantity":1}'
    assert errors(client.post("/items", content=body)) == [("model_attributes_type", ["body"])]
    assert client.post("/items", content=body, headers={"content-type": "application/vnd.api+json"}).status_code == 201
    assert errors(client.post("/items", content=b"", headers={"content-type": "application/json"})) == [("missing", ["body"])]
    assert errors(client.post("/items", content=body + b" x", headers={"content-type": "application/json"})) == [
        ("json_invalid", ["body", 36])]
    bad = client.post("/items", content=b'{"name":"\xe9","price":1,"quantity":1}', headers={"content-type": "application/json"})
    assert (bad.status_code, bad.json()) == (400, {"detail": "There was an error parsing the body"})


def test_routing() -> None:
    create()
    redirect = client.get("/items/?limit=1", follow_redirects=False)
    assert (redirect.status_code, redirect.headers["location"]) == (307, "http://testserver/items?limit=1")
    assert client.get("/Items").json() == {"detail": "Not Found"}
    for method, path, allow in [("PUT", "/items", "POST"), ("PUT", "/items/1", "GET"), ("HEAD", "/health", "GET")]:
        response = client.request(method, path)
        assert (response.status_code, response.headers["allow"]) == (405, allow)


def test_path_and_query_ints() -> None:
    create()
    for raw in ["01", "+1", " 1", "1.0"]:
        assert client.get(f"/items/{raw}").status_code == 200
    assert client.get("/items/1_0").json() == {"detail": "item 10 not found"}
    assert errors(client.get("/items/1e0")) == [("int_parsing", ["path", "item_id"])]
    assert errors(client.get("/items?limit=0&offset=-1")) == [
        ("greater_than_equal", ["query", "limit"]), ("greater_than_equal", ["query", "offset"])]
    assert client.get("/items?limit=1&limit=2").json()["total"] == 1


def test_list_patch_delete_reserve_stats() -> None:
    create(name="a", tags=["x"])
    create(name="b", price=0.1, quantity=3)
    assert client.get("/items?tag=x").json()["total"] == 1
    assert client.patch("/items/2", json={"name": None}).json() == {"detail": "fields cannot be null"}
    assert client.patch("/items/2", json={"price": 0.2}).json()["price"] == 0.2
    assert client.post("/items/2/reserve", json={"quantity": 5}).json() == {
        "detail": "insufficient stock: requested 5, available 3"}
    assert client.post("/items/2/reserve", json={"quantity": 2}).json() == {"item_id": 2, "reserved": 2, "remaining": 1}
    assert client.delete("/items/1").status_code == 204
    assert client.get("/stats").content == b'{"items":1,"total_quantity":1,"total_value":0.2}'
    assert errors(client.patch("/items/99", json={"bogus": 1})) == [("extra_forbidden", ["body", "bogus"])]
