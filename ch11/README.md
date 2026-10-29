# ch11 — Python과 Rust를 함께 쓰기 (PyO3·maturin 부분 이식)

책 11장의 예제입니다. 측정은 WSL2 Ubuntu 24.04(i7-6700K)에서 했습니다(Python 3.12.3, Rust 1.99.1, PyO3 0.30.1, maturin 1.16.0, NumPy 2.5.4).

| 경로 | 내용 | 절 |
|---|---|---|
| `hello_ext/` | PyO3 확장 모듈의 기본(호출, 리스트 변환, 예외, GIL 해제). 저자 작성 | 11-2 |
| `hello_ext/bench_overhead.py` | 호출 비용, 리스트 변환 비용, NumPy 비교, GIL 해제 효과 측정 | 11-1, 11-2 |
| `partial/prompts/partial.md` | logstat(09장)의 해석·검증·집계를 Rust 확장으로 옮기게 한 지시문(경계 두 가지) | 11-3 |
| `partial/run_partial.py` | 8장 파이프라인으로 부분 이식을 실행하고 게이트(fmt, clippy, maturin, 비교, 무작위 비교)를 직접 실행 | 11-3 |
| `partial/phases_ext.py` | 같은 프로세스 안에서 경계별 시간 측정 | 11-3 |
| `results/` | 이 책의 측정 결과 | 11-1 ~ 11-3 |

에이전트가 만든 확장 모듈(`rust_ext/`)과 진입점(`ext/logstat_v1.py`, `ext/logstat_v2.py`)은 `ch08/porter/runs/ch11_partial/workspace/`에 있습니다.

## 실행

```bash
cd ch11/hello_ext
uv sync
uv run maturin develop --release
uv run pytest -q
uv run python bench_overhead.py

# 부분 이식 (ch08/porter 에서, 비용이 듭니다)
uv run python ../../ch11/partial/run_partial.py --run ch11_partial --model sonnet --budget 6
```
