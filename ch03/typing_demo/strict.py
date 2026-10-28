"""타입 힌트와 dataclass로 쓴 주문 합계 계산 (03-1)."""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Item:
    price: int  # 원 단위 정수. 소수점 금액은 받지 않는다
    qty: int = 1


@dataclass(frozen=True)
class FixedCoupon:
    amount: int  # 원


@dataclass(frozen=True)
class PercentCoupon:
    percent: int  # 0~100


Coupon = FixedCoupon | PercentCoupon


@dataclass(frozen=True)
class Order:
    items: list[Item]
    coupon: Coupon | None = None


class OrderError(Exception):
    """입력 주문이 계약을 어겼다."""


def parse_coupon(raw: object) -> Coupon | None:
    if raw is None:
        return None
    if isinstance(raw, int) and not isinstance(raw, bool) and raw >= 0:
        return FixedCoupon(raw)
    if isinstance(raw, str) and raw.endswith("%") and raw[:-1].isascii() and raw[:-1].isdigit():
        percent = int(raw[:-1])
        if percent <= 100:
            return PercentCoupon(percent)
    raise OrderError(f"invalid coupon: {raw!r}")


def parse_order(text: str) -> Order:
    """JSON 문자열 → Order. 파일을 읽지 않는 순수 함수."""
    data = json.loads(text)
    items = [Item(price=int(it["price"]), qty=int(it.get("qty", 1))) for it in data["items"]]
    return Order(items=items, coupon=parse_coupon(data.get("coupon")))


def total(order: Order) -> int:
    """할인 적용 합계(원). 퍼센트 할인은 원 단위 미만을 버린다. 0 아래로 내려가지 않는다."""
    subtotal = sum(item.price * item.qty for item in order.items)
    match order.coupon:
        case None:
            discounted = subtotal
        case FixedCoupon(amount):
            discounted = subtotal - amount
        case PercentCoupon(percent):
            discounted = subtotal * (100 - percent) // 100
    return max(discounted, 0)


def main(argv: list[str]) -> int:
    """입출력은 여기서만 한다."""
    text = Path(argv[0]).read_text(encoding="utf-8")
    try:
        order = parse_order(text)
    except (OrderError, KeyError, ValueError, TypeError) as err:
        print(f"order: error: {err}", file=sys.stderr)
        return 1
    print(total(order))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
