"""17자리 실수에서 pydantic-core 와 Rust 가 고르는 자릿수가 다른 이유를 본다.

사용법: uv run python verify/probe_digits.py
"""

from decimal import Decimal

from pydantic_core import to_json

for v in [654840279078428.2, 75506162623260.12, 147239482226234.62, 2114171160437759.2]:
    exact = Decimal(v)
    pyd = to_json(v).decode()
    print(f"repr={v!r} pydantic={pyd} exact={exact}")
    for cand in (pyd, repr(v)):
        print(f"   {cand}: |diff|={abs(Decimal(cand) - exact)} roundtrip={float(cand) == v}")
    last = Decimal(pyd)
    step = Decimal(1).scaleb(last.as_tuple().exponent)
    for c in (last - step, last + step):
        print(f"   {c}: |diff|={abs(c - exact)} roundtrip={float(c) == v}")
