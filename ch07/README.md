# 07장 예제 — Python·Rust 기능 동등성 검증

WSL2 Ubuntu 24.04(Python 3.12.3 / Unicode 15.0, Rust 1.99.1)에서 측정했습니다.
비교 대상은 04·05장의 wordfreq Rust 구현 세 개(04장 1회차, 05장 2회차, 05장 3회차)이고,
기준 구현은 `ch05/wordfreq/python_src/wordfreq.py` 입니다.

비교 대상 빌드(예):

```bash
cargo build --release --manifest-path ch05/wordfreq/rust_app/Cargo.toml --target-dir ~/work/ch07_target/ch05_run3
cp ~/work/ch07_target/ch05_run3/release/wordfreq ~/work/ch07_bin/ch05_run3
```

| 경로 | 절 | 내용 |
|---|---|---|
| `golden/` | 07-1 | 기준 출력 저장·비교(`golden.py record`/`check`), 추가 케이스, 저장된 기준 출력 `goldens/` |
| `property/` | 07-2 | Hypothesis 비교(`equivalence.py`, `test_equivalence.py`, `hunt.py`), 전수 비교(`sweep_pattern.py`), proptest(`rust_props/`, `run_props.sh`), 측정 결과 `hunt_results.jsonl` |
| `errors/` | 07-3 | 오류·환경·부작용 시나리오 14개(`scenarios.py`, Linux 전용), 결과 `scenario_results.json` |
| `floats/` | 07-4 | 부동소수점 기본 차이(`basics/`), stats 이식 과제(`task/`), 에이전트 실행(`run_port.sh`), 비교 규칙별 평가(`evaluate.py`), 결과 `runs/` |
| `nondet/` | 07-4 | HashMap·dict·set 순서가 실행마다 바뀌는지 세기(`count_orders.sh`) |

```bash
cd ch07/golden && python3 make_fixtures.py && python3 golden.py record
python3 golden.py check --rust ~/work/ch07_bin/ch05_run3

cd ../property && uv sync
uv run python hunt.py ~/work/ch07_bin/ch05_run3 --seeds 1 2 3
RUST_BIN=~/work/ch07_bin/ch05_run3 uv run pytest -q test_equivalence.py

cd ../errors && python3 scenarios.py ~/work/ch07_bin/ch05_run3
```

`golden/fixtures/all_codepoints.txt`(약 23MB)는 저장소에 넣지 않습니다. `make_fixtures.py`로 만드세요.
proptest 는 실패한 입력을 `rust_props/tests/props.proptest-regressions`에 저장하고 다음 실행에서 먼저 시험합니다.
