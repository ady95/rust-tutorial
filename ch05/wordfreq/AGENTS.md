# wordfreq Python → Rust 이식 지침

이 문서는 에이전트 종류와 무관한 이식 규칙이다. Claude Code는 CLAUDE.md에서 이 파일을 불러온다.

## 목표

`python_src/wordfreq.py`(기준 구현)와 같은 동작을 하는 Rust 명령행 프로그램을 `rust_app/`에 만든다.
"같은 동작"의 정의는 `contracts/behavior_spec.md`(동작 계약)와 `tests/cases.json`(비교 케이스)이다.

## 폴더 권한

| 경로 | 권한 |
|---|---|
| `rust_app/` | 읽기·쓰기. Rust 코드는 모두 여기에 |
| `reports/` | 쓰기. 보고서만 |
| `python_src/`, `tests/`, `contracts/`, `automation/`, `baseline.lock`, `pyproject.toml`, `uv.lock`, `.python-version` | 읽기만. 절대 수정하지 않는다 |

기준 구현이나 테스트가 틀렸다고 판단되면 고치지 말고 보고서의 "기준 구현 의심 사항"에 적는다.

## 동작 범위

- 계약에 적힌 것과 `cases.json`에 있는 것만 Python과 같게 만든다
- 계약에서 "비교 안 함"으로 정한 것(인자 오류 메시지 문구)은 Python argparse를 흉내 내지 않는다. 짧은 사용법 한 줄과 오류 한 줄이면 된다
- 계약에 없는 Python의 부수 동작은 재현하지 않는다. 예: argparse의 옵션 이름 줄여 쓰기(`--to`), `int()`의 전각 숫자·밑줄 해석. `--top`은 ASCII 숫자만 받는다
- 단어 규칙(공백 정의, 문장 부호, 소문자 변환)은 계약 2절대로 정확히 맞춘다. 기준 Python은 3.12(Unicode 15.0)다

## 코드 규칙

- Rust stable, edition 2024. 외부 크레이트 없이 표준 라이브러리만 쓴다
- 로직은 `src/lib.rs`, 입출력과 종료 코드는 `src/main.rs`에 둔다. 로직 함수는 파일·표준 입출력에 직접 접근하지 않는다
- 정상 출력은 UTF-8, 줄바꿈은 LF. 운영체제와 무관하다

## 완료 조건

아래가 모두 통과해야 완료다. 하나라도 실패하면 완료라고 보고하지 않는다.

1. `cargo build --release` 성공
2. `cargo fmt --check` 통과
3. `cargo clippy --all-targets -- -D warnings` 통과
4. `cargo test` 통과
5. 프로젝트 폴더에서 `uv run python automation/compare.py`가 종료 코드 0 (모든 케이스 일치)

compare.py가 종료 코드 3을 내면 프로그램을 실행하지 못한 것이다(운영체제 정책 등). 코드 문제가 아니므로 코드를 고치지 말고 보고서에 적는다.

## 보고서

작업을 마치면 `reports/agent_report.md`에 다음을 쓴다.

- 완료 조건 1~5의 결과 (실제로 실행한 것만 "통과"로 적는다)
- 직접 정한 가정
- 기준 구현 의심 사항
- 하지 못한 것과 이유
