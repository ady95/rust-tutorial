"""서로게이트가 든 키가 모델 검증에서 어떤 오류가 되는지 실측.

사용법: STOCKROOM_TEST=1 uv run python verify/probe_surrogate_key.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "python_src"))

from pydantic import ValidationError  # noqa: E402

from stockroom.app import ItemIn, ItemPatch, ReserveIn  # noqa: E402

S = "\udc00"
CASES = [
    (ItemIn, {"name": "a", "price": 1, "quantity": 1, S: 1}),
    (ItemIn, {"name": 5, "price": 1, "quantity": 1, S: 1}),
    (ItemIn, {S: 1, "name": 5, "price": 1, "quantity": 1}),
    (ItemIn, {"x": 1, S: 1, "y": 2}),
    (ItemIn, {S: 1, "x": 1}),
    (ItemIn, {"a" + S: 1, "name": "a", "price": "x"}),
    (ItemIn, {S: 1}),
    (ItemPatch, {S: 1}),
    (ItemPatch, {"name": 5, S: 1, "z": 1}),
    (ReserveIn, {"quantity": 0, S: 1}),
    (ReserveIn, {S: 1, S + "b": 2}),
]
for model, data in CASES:
    try:
        model.model_validate(data)
        print(model.__name__, ascii(data), "OK")
    except ValidationError as err:
        print(model.__name__, ascii(data), [(e["type"], e["loc"]) for e in err.errors()])
