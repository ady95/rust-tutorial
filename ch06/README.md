# 06장 예제 — Rust 컴파일 오류와 자동 수정·종료 조건

06장부터는 WSL2 Ubuntu 24.04에서 측정했습니다(Rust 1.99.1, Python 3.12.3, Claude Code 2.1.299).

## ownership/ (06-1, 06-2)

| 경로 | 내용 |
|---|---|
| `broken/` | Python 습관대로 옮겨 컴파일에 실패하는 예제 6개(E0382·E0502·E0499·E0106·E0515·E0597) |
| `check_samples.py` | 각 예제가 파일 이름의 오류 코드로 실패하는지 확인하고, 진단을 human·short·json 세 형식으로 `diagnostics/`에 저장 |
| `python_habits.py` | 같은 코드를 Python으로 실행한 결과 |
| `fixed/` | 고친 크레이트와 테스트 |

```bash
cd ch06/ownership
python3 check_samples.py
python3 python_habits.py
cd fixed && cargo test
```

## fixloop/ (06-2 ~ 06-4)

에이전트에게 고치게 하는 작은 크레이트 `wordstats`와 실험 도구입니다.

| 경로 | 내용 |
|---|---|
| `task/` | 에이전트가 받는 크레이트. `src/lib.rs`에 컴파일 오류 6개, 동작 버그 2개, Clippy 경고 거리 3개가 들어 있음. `tests/spec.rs`·`python_src/`는 기준(수정 금지) |
| `answer/src/lib.rs` | 정답. U+001C..U+001F 공백 처리는 runC 에이전트가 찾은 것을 나중에 반영 |
| `settings/`, `hooks/` | 권한 규칙(거부 목록)과 훅. `after_edit.py`(fmt+check), `before_stop.py`(fmt·clippy·test, 연속 3회 상한) |
| `run_agent.py` | `task/`를 새 폴더에 복사해 Claude Code로 고치게 하고 채점(`runs/<이름>/metrics.json`) |
| `retry_loop.py` | 바깥 재시도 루프. 성공·진전 없음·시도 상한·비용 상한 중 먼저 걸리는 조건에서 멈춤 |
| `regrade.py` | 저장된 결과를 현재 채점 기준으로 다시 채점 |
| `compile_only_fix.py` | 컴파일 오류만 최소로 고친 버전을 만들어 무엇이 남는지 확인 |
| `extra/contradiction.rs` | 06-4 실험용. `spec.rs`와 모순되는 테스트 |
| `runs/` | 실행별 결과(metrics.json, 고친 lib.rs, diff, 에이전트 보고서, 훅 기록) |
| `run_logs/` | 실행 기록. 측정 PC의 환경 정보(설치된 도구 목록 등)를 지운 사본 |

### 실행 예

실행 전에 `settings/`와 `hooks/`를 읽어 보세요. 훅은 임의의 명령을 실행할 수 있습니다(05-3).

```bash
cd ch06/fixloop
mkdir -p ~/ch06_raw   # 실행 기록 원본은 저장소 밖에 둡니다
python3 run_agent.py myrun --settings no_hooks --allowed "Bash(cargo *)" \
  --max-turns 40 --max-budget-usd 4 --raw-dir ~/ch06_raw
python3 retry_loop.py myloop --extra-test extra/contradiction.rs \
  --attempts 3 --budget-usd 4 --raw-dir ~/ch06_raw
```

에이전트 출력은 실행할 때마다 달라집니다. 같은 채점(`grade`)을 통과하면 정상입니다.
비용은 Claude Code가 계산한 추정치이며 실제 청구액과 다를 수 있습니다.
