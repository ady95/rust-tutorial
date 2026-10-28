@AGENTS.md

## Claude Code 전용 메모

- 이 프로젝트의 `.claude/settings.json`이 기준 폴더 수정과 git·네트워크 사용을 막는다. 막힌 작업은 우회하지 말고 보고서에 적는다
- `.rs` 파일을 쓰거나 고치면 훅이 `cargo fmt`를 자동으로 실행한다. 형식은 신경 쓰지 않아도 된다
- 작업을 끝내려 하면 훅이 완료 조건(기준 고정, fmt, clippy, test, release 빌드, compare.py)을 검사한다. 실패하면 그 결과가 전달되니 고친 뒤 다시 끝낸다
- 셸 명령은 Cargo와 `uv run python automation/compare.py`만 허용된다
