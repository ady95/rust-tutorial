"""stockroom: 재고 관리 API (10장 기준 구현, FastAPI).

동작 계약은 contracts/behavior_spec.md 에 있다. 이 파일이 그 계약의 기준 구현이다.
상태는 메모리에만 있다. 환경 변수 STOCKROOM_TEST=1 이면 POST /_test/reset 으로 상태를 비울 수 있다(비교 시험용).
"""

from __future__ import annotations

import os
from typing import Annotated

from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

app = FastAPI(title="stockroom")


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
    # FastAPI 기본 처리기는 오류 본문에 입력값(input)을 넣는데, 본문의 NaN·Infinity 가 입력값이면
    # JSON 으로 만들지 못해 500 이 된다(10-1에서 발견). 그래서 type, loc, msg 만 돌려준다(계약 4절)
    errors = [{"type": e["type"], "loc": list(e["loc"]), "msg": e["msg"]} for e in exc.errors()]
    return JSONResponse(status_code=422, content={"detail": errors})

Name = Annotated[str, Field(min_length=1, max_length=100)]
Price = Annotated[float, Field(ge=0, le=1_000_000)]
Quantity = Annotated[int, Field(ge=0, le=1_000_000)]
Tags = Annotated[list[Annotated[str, Field(min_length=1, max_length=20)]], Field(max_length=10)]


class ItemIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: Name
    price: Price
    quantity: Quantity
    tags: Tags = []


class ItemPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: Name | None = None
    price: Price | None = None
    quantity: Quantity | None = None
    tags: Tags | None = None


class Item(BaseModel):
    id: int
    name: str
    price: float
    quantity: int
    tags: list[str]


class ReserveIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    quantity: Annotated[int, Field(gt=0, le=1_000_000)]


class Store:
    def __init__(self) -> None:
        self.items: dict[int, Item] = {}
        self.next_id = 1

    def get(self, item_id: int) -> Item:
        item = self.items.get(item_id)
        if item is None:
            raise HTTPException(status_code=404, detail=f"item {item_id} not found")
        return item


store = Store()


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/items", status_code=201)
async def create_item(body: ItemIn, response: Response) -> Item:
    item = Item(id=store.next_id, **body.model_dump())
    store.items[item.id] = item
    store.next_id += 1
    response.headers["Location"] = f"/items/{item.id}"
    return item


@app.get("/items")
async def list_items(
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
    tag: str | None = None,
) -> dict[str, object]:
    matched = [item for item in store.items.values() if tag is None or tag in item.tags]
    return {"items": matched[offset:offset + limit], "total": len(matched)}


@app.get("/items/{item_id}")
async def get_item(item_id: int) -> Item:
    return store.get(item_id)


@app.patch("/items/{item_id}")
async def update_item(item_id: int, body: ItemPatch) -> Item:
    item = store.get(item_id)
    changes = body.model_dump(exclude_unset=True)
    if any(value is None for value in changes.values()):
        raise HTTPException(status_code=400, detail="fields cannot be null")
    updated = item.model_copy(update=changes)
    store.items[item_id] = updated
    return updated


@app.delete("/items/{item_id}", status_code=204)
async def delete_item(item_id: int) -> Response:
    store.get(item_id)
    del store.items[item_id]
    return Response(status_code=204)


@app.post("/items/{item_id}/reserve")
async def reserve(item_id: int, body: ReserveIn) -> dict[str, int]:
    # async 함수 안에서 await 없이 확인과 갱신을 하므로, 이벤트 루프 하나에서는 다른 요청이 끼어들 수 없다
    item = store.get(item_id)
    if body.quantity > item.quantity:
        raise HTTPException(status_code=409,
                            detail=f"insufficient stock: requested {body.quantity}, available {item.quantity}")
    store.items[item_id] = item.model_copy(update={"quantity": item.quantity - body.quantity})
    return {"item_id": item_id, "reserved": body.quantity, "remaining": item.quantity - body.quantity}


@app.get("/stats")
async def stats() -> dict[str, object]:
    items = list(store.items.values())
    return {
        "items": len(items),
        "total_quantity": sum(item.quantity for item in items),
        "total_value": sum(item.price * item.quantity for item in items),  # Python sum(): 보정 합산(07-4)
    }


if os.environ.get("STOCKROOM_TEST") == "1":

    @app.post("/_test/reset", status_code=204)
    async def reset() -> Response:
        store.__init__()
        return Response(status_code=204)
