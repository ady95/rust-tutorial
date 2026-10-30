#!/usr/bin/env bash
# 같은 프로그램을 N 번 실행해 줄마다 서로 다른 출력이 몇 가지 나오는지 센다 (07-4)
# 사용법 (ch07/nondet 에서): bash count_orders.sh [N]
set -u
N="${1:-50}"
HERE="$(cd "$(dirname "$0")" && pwd)"
cargo build -q --release --manifest-path "$HERE/hash_order/Cargo.toml"
BIN="$HERE/hash_order/target/release/hash_order"
for i in $(seq "$N"); do "$BIN"; done > /tmp/rust_orders.txt
for i in $(seq "$N"); do python3 "$HERE/hash_order.py"; done > /tmp/py_orders.txt
for i in $(seq "$N"); do PYTHONHASHSEED=0 python3 "$HERE/hash_order.py"; done > /tmp/py_fixed.txt
echo "runs: $N"
for prefix in "hash:" "tree:"; do
  echo "rust $prefix $(grep "^$prefix" /tmp/rust_orders.txt | sort -u | wc -l) distinct"
done
for prefix in "dict:" "set: "; do
  echo "python $prefix $(grep "^$prefix" /tmp/py_orders.txt | sort -u | wc -l) distinct"
done
echo "python set: with PYTHONHASHSEED=0: $(grep '^set: ' /tmp/py_fixed.txt | sort -u | wc -l) distinct"
