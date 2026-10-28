# 05장 예제 — 프로젝트 단위 지침·권한·훅으로 다시 변환하기

| 경로 | 내용 |
|---|---|
| `wordfreq/` | 04장과 같은 기준 구현에 지침(`AGENTS.md`, `CLAUDE.md`)과 설정(`.claude/`)을 더한 프로젝트. `rust_app/`은 3회차 결과 |
| `wordfreq/.claude/settings.json` | 권한 규칙(허용·거부)과 훅 등록 (05-3) |
| `wordfreq/.claude/hooks/` | 파일 수정 후 `cargo fmt`, 종료 직전 완료 조건 검사 (05-3) |
| `wordfreq/reports/` | 3회차 에이전트 보고서, 완료 검사 기록, 사람 리뷰 기록(`review.md`) |
| `runs/run2/` | 2회차 결과(에이전트가 Cargo를 실행하지 못한 회차). 테스트 1개 실패, 넓은 입력에서 멈춤 — 기록용으로 보존 |
| `run_logs/` | 실행 기록. 측정 PC의 환경 정보(설치된 도구 목록, 사용자 경로)는 지운 사본 |
| `review/unicode_sweep.py` | 모든 Unicode 코드 포인트로 Python·Rust 출력 비교 (05-5) |
| `prompt.txt` | 2·3회차에 쓴 한 문장 프롬프트 |

## 주의: 실행 전에 `.claude/`를 읽어 보세요

`claude -p`(헤드리스 모드)는 처음 받은 저장소라도 `.claude/settings.json`에 등록된 훅을 실행합니다. 훅은 임의의 명령을 실행할 수 있으므로, 남의 저장소에서 실행하기 전에 설정과 훅 스크립트를 먼저 확인하세요. 반대로 허용(`allow`) 규칙은 대화형 모드에서 폴더를 신뢰하기 전까지 무시되므로, 실행 명령에 `--allowedTools`를 함께 줍니다(05-3).

```powershell
cd ch05\wordfreq
cargo --version   # 먼저 Cargo가 PATH에 있는지 확인 (05-1)
claude -p (Get-Content ..\prompt.txt -Raw -Encoding UTF8) `
  --permission-mode acceptEdits `
  --allowedTools "Bash(cargo *)" "PowerShell(cargo *)" `
    "Bash(uv run python automation/compare.py)" "PowerShell(uv run python automation/compare.py)" `
  --strict-mcp-config --max-turns 80 `
  --output-format stream-json --verbose > ..\run_logs\my_run.jsonl
```

에이전트 출력은 실행할 때마다 달라집니다. 같은 검사(`compare.py`, 훅의 완료 조건)를 통과하면 정상입니다.
