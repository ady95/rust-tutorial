# 03장 예제 — Rust 변환을 고려한 Python 프로그램 작성하기

| 폴더 | 절 | 내용 |
|---|---|---|
| `typing_demo` | 03-1 | 타입 힌트 없는 `loose.py`와 있는 `strict.py`, 각각을 Claude Code가 Rust로 옮긴 결과 |
| `diff_demo` | 03-2 | 같은 연산을 Python과 Rust로 실행해 결과가 다른 지점을 나란히 출력 |
| `test_strength` | 03-3 | 기준 구현에 작은 결함을 넣고 pytest와 바이트 비교가 잡아내는지 확인 |

기준 구현 고정 도구는 저장소 최상위 `tools/baseline.py`에 있습니다(03-4).

```bash
# typing_demo — 에이전트 결과 빌드 후 비교
cd ch03/typing_demo
cargo build --release --manifest-path agent_loose/Cargo.toml
uv run --no-project python compare_agents.py loose agent_loose/target/release/order.exe

# diff_demo
cd ch03/diff_demo
cargo build --release --manifest-path rust_side/Cargo.toml
uv run --no-project python compare_sides.py

# test_strength — ch04/wordfreq 의 pytest 환경을 쓴다
cd ch04/wordfreq
uv run python ../../ch03/test_strength/mutate.py
```

`typing_demo/agent_*`의 Rust 코드는 책을 쓸 때 Claude Code가 생성한 그대로입니다(rustfmt 미적용). 에이전트 출력은 실행할 때마다 달라질 수 있습니다. 실행 기록과 비교 결과는 `typing_demo/reports/`에 있습니다.
