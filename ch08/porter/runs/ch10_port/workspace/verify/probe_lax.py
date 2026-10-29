"""pydantic lax 변환을 직접 불러 규칙을 실측한다(구현 전 탐색용).

사용법: uv run python verify/probe_lax.py
"""

from __future__ import annotations

from typing import Annotated

from pydantic import Field, TypeAdapter, ValidationError

INT = TypeAdapter(int)
FLOAT = TypeAdapter(float)
NAME = TypeAdapter(Annotated[str, Field(min_length=1, max_length=100)])
QTY = TypeAdapter(Annotated[int, Field(ge=0, le=1_000_000)])
PRICE = TypeAdapter(Annotated[float, Field(ge=0, le=1_000_000)])


def run(adapter: TypeAdapter, value: object) -> str:
    try:
        return "OK " + repr(adapter.validate_python(value))
    except ValidationError as err:
        return "ERR " + ",".join(e["type"] for e in err.errors())
    except Exception as err:  # noqa: BLE001
        return "EXC " + type(err).__name__


INT_INPUTS = ["5", "05", "+1", "-1", "-0", " 5 ", "5_0", "5.0", "5.", "5.000", ".0", "_5", "5_", "5__0", "-05",
              "\xa05", "　5", "\x1c5", "5\x1c", "\x855", "+-1", "+_5", "-_5", "5_.0", "5.0_0", "5._0", "1_0.0",
              "0_0", "00", "0x1", "1e1", "", " ", "٥", "１", "+", "-", "5 .0", "5.0 ", " 5.0", "99999999999999999999",
              "9" * 19, "9" * 39, "9" * 40, "-" + "9" * 40, "1" * 4300, "1" * 4301, " " + "1" * 4300, "0" * 4301,
              "5.00000000000000000001", "1_000_000_000_000_000_000", "1__000_000_000_000_000_000_000",
              "\t5", "5\n", "\v5", "\f5", "\r5", " 5", "\u00855", "᠎5", "﻿5", "5\x00",
              "1" * 18 + "_1", "1" * 19 + "__1", "_" + "1" * 20, "1" * 20 + "_", "+" + "1" * 20, "+0", "-0.0", "+5.0",
              "1" * 20 + ".0", "1" * 20 + ".", "1" * 20 + ".00", "1_" * 10 + "1.0"]
FLOAT_INPUTS = ["12.5", " 2 ", "1_0.5", "1e-5", "true", "0x1p3", "inf", "nan", "1__0", "_1", "1_", "1_e5", "Infinity",
                "-inf", "NAN", "+1.5", ".5", "5.", "1e", "١.5", "-0", " 1_0.5", "1_0.5 ", "1_0 ", "infinity", "+inf",
                "-nan", "1e400", "-1e400", "1E5", "1.5e+3", " ", "", "e5", ".", "1_000.000_1", "\x1c1", "1.0_", "_",
                "1._5", "1_.5", "\xa01_0", "inF", "iNfInItY", "nAn", "+nan", "1e1_0", "0_0"]
OTHER = [True, False, None, 3.5, 3.0, -0.0, float("nan"), float("inf"), float("-inf"), 1e30, 10**30, -(10**30),
         10**400, 2**63, -(2**63), 2**63 - 1, 9.2e18, 9.3e18, [], {}, b"5", "\ud800", "a\udc00"]


def main() -> None:
    for s in INT_INPUTS + OTHER:
        print(f"int   {s!r:.60}: {run(INT, s)[:80]}")
    for s in FLOAT_INPUTS + OTHER:
        print(f"float {s!r:.60}: {run(FLOAT, s)[:80]}")
    for v in [float("nan"), float("inf"), float("-inf"), -0.0, 10**400, 10**30, 1e300 * 10, "nan", "-inf"]:
        print(f"price {v!r:.40}: {run(PRICE, v)}")
    for v in [float("nan"), float("inf"), 10**30, -(10**30), 1e30, -0.0, "1e3", 10**400]:
        print(f"qty   {v!r:.40}: {run(QTY, v)}")
    for v in ["\ud800", "a\udc00b", "😀", "", "x" * 101]:
        print(f"name  {v!r:.40}: {run(NAME, v)}")


if __name__ == "__main__":
    main()
