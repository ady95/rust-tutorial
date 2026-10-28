"""타입 힌트 없이 쓴 주문 합계 계산 (03-1, 비교용 나쁜 예)."""

import json
import sys


def total(order):
    if not order["items"]:
        return None
    s = 0
    for it in order["items"]:
        s += it["price"] * it.get("qty", 1)
    c = order.get("coupon")
    if isinstance(c, str) and c.endswith("%"):
        s = s * (100 - int(c[:-1])) / 100
    elif c:
        s -= c
    return s


if __name__ == "__main__":
    print(total(json.load(open(sys.argv[1]))))
