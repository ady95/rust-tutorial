"""일부러 원자성을 깬 기준 구현 변형 (10-4). 동시 요청 시험이 경쟁 조건을 실제로 잡는지 확인하는 용도다.

reserve 를 async 가 아닌 일반 함수(def)로 바꾸면 FastAPI 는 스레드 풀에서 실행한다. 확인과 차감 사이에
잠깐 쉬게 하면 여러 요청이 같은 수량을 보고 함께 차감해, 처음 수량보다 많이 예약된다.
현실에서도 동기 함수 안에서 DB 를 읽고 쓰는 코드가 이런 식으로 깨진다.

사용법: python3 racy_server.py --port P   (STOCKROOM_TEST=1 이면 /_test/reset 도 있음)
"""

import argparse
import sys
import time
from pathlib import Path

import uvicorn

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "stockroom" / "python_src"))

from stockroom import app as module  # noqa: E402

app = module.app
app.router.routes = [r for r in app.router.routes if getattr(r, "path", "") != "/items/{item_id}/reserve"]


@app.post("/items/{item_id}/reserve")
def reserve(item_id: int, body: module.ReserveIn) -> dict[str, int]:
    item = module.store.get(item_id)
    if body.quantity > item.quantity:
        raise module.HTTPException(status_code=409,
                                   detail=f"insufficient stock: requested {body.quantity}, available {item.quantity}")
    time.sleep(0.001)  # 확인과 차감 사이의 틈(실제 코드에서는 DB 왕복 등)
    module.store.items[item_id] = item.model_copy(update={"quantity": item.quantity - body.quantity})
    return {"item_id": item_id, "reserved": body.quantity, "remaining": item.quantity - body.quantity}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    uvicorn.run(app, host="127.0.0.1", port=args.port, workers=1, access_log=False, log_level="warning")
