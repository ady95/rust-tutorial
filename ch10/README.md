# ch10 — Python API 서버(FastAPI)를 Rust로 자동 구현

책 10장의 예제입니다. 재고 관리 API `stockroom`을 FastAPI로 만들고, 8장의 파이프라인(`ch08/porter`)으로 Rust로 옮긴 뒤 계약·동시성·성능을 검증합니다.
측정은 WSL2 Ubuntu 24.04(i7-6700K)에서 했습니다(Python 3.12.3, FastAPI 0.162.0, uvicorn 0.54.0, Rust 1.99.1).

| 경로 | 내용 | 절 |
|---|---|---|
| `stockroom/` | FastAPI 기준 구현, 계약, pytest, 요청열 케이스, HTTP 비교 도구(`http_diff.py`, `compare.py`, `fuzz.py`), `port.json`, `baseline.lock` | 10-1 |
| `bench/prompts/axum.md` | 첫 이식 결과의 HTTP 계층을 axum·tokio로 바꾸게 한 지시문(`ch09/bench/variant.py`로 실행) | 10-2 |
| `bench/race.py` | 동시 예약·동시 생성 시험(계약 5절) | 10-4 |
| `bench/variants/racy_server.py` | 일부러 원자성을 깬 Python 변형(시험이 경쟁 조건을 잡는지 확인용) | 10-4 |
| `bench/load.py`, `bench/run_load.py` | 표준 라이브러리만 쓰는 부하 생성기와 서버별 측정 | 10-4 |
| `bench/results/` | 이 책의 측정 결과 | 10-3, 10-4 |

에이전트가 만든 Rust 코드와 실행 기록은 `ch08/porter/runs/ch10_analyze/`, `ch10_port/`(표준 라이브러리로 HTTP까지 직접 쓴 버전), `ch10_axum/`(HTTP 계층을 axum으로 바꾼 버전)에 있습니다. 저수준 HTTP 비교 스크립트는 `ch10_port/workspace/verify/http_raw.py`(에이전트 작성)입니다.

## 실행

```bash
cd ch10/stockroom
uv sync && uv run pytest -q
STOCKROOM_TEST=1 uv run python python_src/run_server.py --port 8000

# 비교 (Rust 실행 파일이 있을 때)
uv run python automation/compare.py --rust <stockroom 실행 파일>
uv run python automation/fuzz.py --rust <stockroom 실행 파일> --examples 400

# 동시성·부하 (ch10/bench 에서, 서버 명령은 --port 를 받아야 함)
python3 race.py --repeat 5 -- <서버 실행 명령>
python3 run_load.py --name rs --out results/my.json -- <서버 실행 명령>
```

## 주의

부하 측정의 클라이언트(`load.py`)는 Python이라, 빠른 서버에서는 클라이언트가 먼저 한계에 닿습니다. Rust 서버의 처리량은 하한으로 읽고, 요청당 서버 CPU 시간을 함께 보세요.
`STOCKROOM_TEST=1`이면 상태를 비우는 `POST /_test/reset`이 열립니다. 시험용이므로 운영 환경에서는 켜지 마세요.
