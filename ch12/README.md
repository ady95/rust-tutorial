# 12장. 사람은 Python만 개발하는 Rust 자동 개발 시스템

- `rustify/` : 최종 도구. 8장 파이프라인(ch08/porter)을 정리하고 입력 검사·범용 비교 하네스·성능 측정·보고서·재현 검사를 더함
- `projects/mdtoc/` : 이 장의 실습 프로젝트(Markdown 목차). 사람이 Python 으로만 만든 기준 구현·테스트·계약(2판)
- `rustify/runs/` : 실측 기록(에이전트 로그는 측정 환경 정보를 지운 사본, 실행 파일은 해시만)

```bash
cd ch12/rustify
uv sync
uv run python rustify.py check ../projects/mdtoc
uv run python rustify.py run ../projects/mdtoc --run my_run --model sonnet --budget 6
uv run python rustify.py bench --run my_run
uv run python rustify.py report --run my_run
uv run python rustify.py replay --run my_run
```

Linux·WSL 기준(bubblewrap 필요). 에이전트 인증은 Claude Code 로그인(또는 `.env` 의 API 키)을 그대로 쓴다.
`--dangerously-skip-permissions` 같은 무제한 실행은 쓰지 않는다. 권한은 정책 훅과 샌드박스가 정한다.

| 실행 | 내용 |
|---|---|
| mdtoc_s1 | 1판 새 이식(분석·이식·후속 확인) |
| mdtoc_s2 | 2판 증분 이식(`--from mdtoc_s1`) |
| wordfreq_v3 | 8장 wordfreq 3판 증분 이식(8장 single2 에서 시작) |
| fail_input | 승인 뒤 바뀐 입력(입력 검사에서 멈춤) |
| fail_budget | 예산 0.5달러, 분석·후속 확인 없음(게이트 통과, 숨긴 평가 실패: hidden_eval.md) |
| fail_budget2 | 예산 0.15달러(budget 으로 멈춤) |
| mdtoc_codex | 2판 새 이식, Codex 엔진(`--engine codex`, 분석 없음). 숨긴 평가·교차 탐침·성능 비교: hidden_eval.md |
| mdtoc_claude_na | 같은 조건의 Claude 엔진(비교 기준) |

Codex 엔진은 Codex CLI 와 같은 릴리스의 `codex-code-mode-host` 가 함께 설치되어 있어야 셸 명령을 실행한다(0.162.1 기준).
Codex 의 `workspace-write` 샌드박스는 작업 폴더 밖 쓰기와 네트워크를 막지만 읽기는 막지 않는다. 전용 계정에서 실행할 것.
