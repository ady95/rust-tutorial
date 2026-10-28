"""Python과 Rust가 다르게 동작하는 지점을 한 줄씩 출력한다 (03-2).

rust_side/src/main.rs 와 같은 항목 이름을 같은 순서로 출력한다.
compare_sides.py 가 두 출력을 나란히 놓고 비교한다.
"""

import sys

sys.stdout.reconfigure(encoding="utf-8", newline="\n")


def show(name: str, value: object) -> None:
    print(f"{name}\t{value}")


def try_int(text: str) -> str:
    try:
        return str(int(text))
    except ValueError:
        return "error"


# 1. 정수 나눗셈과 나머지 (음수)
show("int.div(-7,2)", -7 // 2)
show("int.rem(-7,2)", -7 % 2)

# 2. 정수 범위
show("int.max_i64_plus_1", 2**63 - 1 + 1)

# 3. 부동소수점 → 문자열
show("float.str(1.0)", str(1.0))
show("float.str(0.1+0.2)", str(0.1 + 0.2))
show("float.str(1e16)", str(1e16))
show("float.str(1e-7)", str(1e-7))
show("float.str(-0.0)", str(-0.0))
show("float.str(nan)", str(float("nan")))
show("float.fmt2(0.125)", f"{0.125:.2f}")
show("float.fmt2(0.375)", f"{0.375:.2f}")
show("float.fmt2(2.675)", f"{2.675:.2f}")
show("float.round(0.5)", round(0.5))
show("float.round(2.5)", round(2.5))

# 4. 문자열 길이와 대소문자
show("str.len(한글)", len("한글"))
show("str.upper(straße)", "straße".upper())

# 5. 문자열 → 정수
show("parse(' 42 ')", try_int(" 42 "))
show("parse('4_2')", try_int("4_2"))
show("parse('+42')", try_int("+42"))
show("parse('４２')", try_int("４２"))

# 6. 해시 컬렉션 순회 순서
show("set.order", " ".join(s for s in {"apple", "banana", "cherry", "durian"}))
show("dict.order", " ".join({"apple": 1, "banana": 2, "cherry": 3, "durian": 4}))
