"""Python 3.12 의 부동소수점 동작 몇 가지 (07-4). Rust 쪽은 src/main.rs."""

print("sum([0.1]*10):", repr(sum([0.1] * 10)))
print("sum([1e16, 1.0, -1e16]):", repr(sum([1e16, 1.0, -1e16])))
for x in [0.125, 0.375, 2.675]:
    print(f"round({x}, 2):", repr(round(x, 2)))
for x in [1.0, 1e16, 1e-5, 0.1 + 0.2, 123456789.0]:
    print(f"repr {x!r}: str={x} / repr={x!r}")
print("format .4 of 0.00005:", f"{0.00005:.4f}")
print("format .4 of 0.00015:", f"{0.00015:.4f}")
