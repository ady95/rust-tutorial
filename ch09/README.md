# ch09 — 데이터 처리 프로그램(logstat)을 Rust로 자동 구현

책 9장의 예제입니다. CSV·JSON Lines 접근 로그를 요약하는 CLI `logstat`을 Python으로 만들고, 8장의 파이프라인(`ch08/porter`)으로 Rust로 옮긴 뒤 처리량·지연시간·메모리를 비교합니다.
측정은 WSL2 Ubuntu 24.04(i7-6700K)에서 했습니다(Python 3.12.3, Rust 1.99.1, hyperfine 1.18).

| 경로 | 내용 | 절 |
|---|---|---|
| `logstat/` | Python 기준 구현, 계약, pytest, 비교 케이스, 비교 도구(`compare.py`, `fuzz.py`), `port.json`, `baseline.lock` | 09-1 |
| `bench/gen_logs.py` | 벤치마크 데이터 생성(seed 고정, CSV와 JSON Lines를 같은 레코드로) | 09-1 |
| `bench/run_bench.py` | hyperfine + 최대 RSS 측정. 측정 전에 모든 구현의 출력이 같은지 확인 | 09-3 |
| `bench/py_phases.py` | Python 기준 구현의 단계별 시간 | 09-4 |
| `bench/variants/logstat_stream.py` | Python "한 번 읽으며 집계" 변형(사람 작성) | 09-4 |
| `bench/variant.py`, `bench/prompts/streaming.md` | 에이전트에게 Rust "한 번 읽으며 집계" 변형을 만들게 하는 스크립트와 지시문 | 09-4 |
| `bench/results/` | 이 책의 측정 결과(JSON, 텍스트) | 09-3, 09-4 |

에이전트가 만든 Rust 코드와 실행 기록은 `ch08/porter/runs/ch09_analyze/`, `ch09_port/`(이식), `ch09_stream/`(변형)에 있습니다.

## 실행

```bash
# 데이터 만들기 (100만 레코드: CSV 60MB, JSONL 119MB)
python3 ch09/bench/gen_logs.py --records 1000000 --out ~/work/ch09_data/logs_1000000

# 이식 (ch08/porter 에서, 비용이 듭니다)
uv run python porter.py analyze ../../ch09/logstat --run ch09_analyze
uv run python porter.py port ../../ch09/logstat --run ch09_port --plan runs/ch09_analyze/plan.json \
  --mode single --policy v2 --allow-crates
uv run python porter.py followup --run ch09_port

# 측정 (ch09/bench 에서)
python3 run_bench.py --impl py="python3 ../logstat/python_src/logstat.py" --impl rs=<Rust 실행 파일> \
  --data ~/work/ch09_data/logs_1000000.csv --records 1000000 --runs 10 --out results/my_run.json
```

## 주의

측정값은 이 PC의 WSL2에서 한 번 측정한 것입니다. 다른 환경에서는 절대값이 다릅니다. 에이전트가 만든 Rust 코드는 다시 실행하면 달라집니다.
