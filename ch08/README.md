# ch08 — Python → Rust 자동 변환 파이프라인

책 8장의 예제입니다. Claude Agent SDK(Python)로 분석 → 구현 → 검증 → 수정 루프를 실행합니다.
측정은 WSL2 Ubuntu 24.04에서 했습니다(Claude Code 2.1.299, Claude Agent SDK 0.2.174, Rust 1.99.1, Python 3.12.3).

| 폴더 | 내용 | 절 |
|---|---|---|
| `projects/wordfreq/` | 기준 구현 2판(07장 결정 반영), 계약, 테스트, 비교 도구(`compare.py`, `scenarios.py`, `fuzz.py`), `baseline.lock` | 08-1 |
| `projects/stats/` | 07-4의 stats 기준 구현 2판(inf·nan은 오류), 계약, 비교 케이스 | 08-1, 08-2 |
| `porter/porter.py` | 파이프라인: `analyze`, `port`, `followup`, `heldout`, `report` | 08-2 ~ 08-6 |
| `porter/porter_lib/` | `agent.py`(SDK 세션), `policy.py`(정책 훅·샌드박스), `gate.py`(검증 게이트), `prompts.py`, `report.py` | |
| `porter/examples/` | 헤드리스 모드와 SDK 비교, 정책·샌드박스 점검 | 08-1, 08-5 |
| `porter/runs/` | 이 책의 실행 기록(실행 파일 제외, `events.jsonl`은 환경 정보를 지운 사본) | |
| `heldout/` | 루프가 끝난 뒤에만 쓰는 평가: 숨긴 평가(`evaluate.py`), 계획의 위험 점검(`plan_probes.py`) | 08-3 |

## 실행

```bash
# 준비 (Linux·WSL2). 샌드박스(정책 2판)에는 bubblewrap 이 필요합니다
sudo apt-get install bubblewrap socat
cd ch08/porter && uv sync

uv run python porter.py analyze ../projects/wordfreq --run analyze_wordfreq
uv run python porter.py port ../projects/wordfreq --run my_run \
  --plan runs/analyze_wordfreq/plan.json --mode single --policy v2 --budget 10
uv run python porter.py followup --run my_run     # 선택: 미검증 항목 확인 라운드
uv run python porter.py heldout --run my_run
uv run python porter.py report --run my_run
```

- 작업 폴더는 `~/work/ch08_ws/<실행 이름>`에 새로 만듭니다
- 에이전트 인증은 Claude Code 로그인(또는 `ANTHROPIC_API_KEY`)을 그대로 씁니다. 키는 `.env` 등 저장소 밖에 두세요
- `porter_lib/agent.py`의 `CLI_PATH`는 설치한 Claude Code(`~/.local/bin/claude`)를 가리킵니다. SDK에 든 Claude Code를 쓰려면 환경 변수 `PORTER_CLAUDE_CLI`를 바꾸세요
- 비용이 듭니다. 이 책의 실행은 한 번에 0.8~8.3달러(추정)였습니다

## 주의

`runs/`의 Rust 코드는 측정 당시 에이전트가 생성한 것입니다. 같은 명령을 다시 실행해도 다른 코드가 나옵니다.
정책 훅은 문자열 규칙이라 완전한 격리가 아닙니다. 에이전트에게 셸을 맡길 때는 샌드박스를 켜고, 사람의 파일은 `baseline.lock`으로 확인하세요.
