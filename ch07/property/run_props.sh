#!/usr/bin/env bash
# rust_props 의 속성 테스트를 5장 3회차(기본)와 5장 2회차에 각각 돌린다 (07-2)
# 사용법 (ch07/property 에서): bash run_props.sh
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
for target in "ch05/wordfreq/rust_app:ch05_run3" "ch05/runs/run2:ch05_run2"; do
  path="${target%%:*}"; name="${target##*:}"
  work="$(mktemp -d)"
  cp -r "$HERE/rust_props/." "$work/"
  sed -i "s|path = \".*\"|path = \"$HERE/../../$path\"|" "$work/Cargo.toml"
  echo "== $name"
  (cd "$work" && cargo test --release -q --test props 2>&1 | grep -E "^test |test result|minimal failing input|Test failed|panicked at" | head -20)
  rm -rf "$work"
done
