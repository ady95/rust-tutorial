# 숨긴 평가와 비교 (2026-10-30, 실행이 끝난 뒤 사람이 따로 실행)

같은 조건(mdtoc 2판, 새로 이식, 분석 없음, 후속 확인 있음, 크레이트 금지)으로 두 엔진을 실행했다.

- mdtoc_codex: Codex CLI 0.162.1, gpt-6.1-sol
- mdtoc_claude_na: Claude Code 2.1.299, sonnet

## 1. mdtoc_s2 의 검증 스크립트(숨긴 평가)

fail_budget 과 같은 방법. s2 의 verify/ 를 작업 폴더의 xverify/ 에 복사해 실행했다.

| 검사 | mdtoc_codex | mdtoc_claude_na |
|---|---|---|
| exhaustive_codepoints (1,112,064 코드 포인트 × 15 맥락) | 다른 묶음 0 | 다른 묶음 0 |
| slug_numbered (7,452건) | 0 | 0 |
| args_diff 깊이 3 (8,421 인자 목록) | 1,021 | 0 |

mdtoc_codex 의 1,021건은 모두 도움말 옵션(`-h`, `--help`, `-hh`, `-hx`)이 든 인자 목록에서
Python 0(도움말) / Rust 2(사용법 오류)였다. 예: `-hx`, `--bogus -h`, `--js --help`.
Codex 는 이것을 노트 3절 "사람이 결정할 계약·기준 구현의 차이"에 적고 고치지 않았다.
계약은 `-h` 는 0, 알 수 없는 옵션은 2 라고만 하고 둘이 함께 올 때의 순서를 정하지 않는다.

## 2. 교차 탐침(examples/cross_probe.py)

Codex 노트가 찾은 가장자리 항목을 모든 2판 실행 파일에 똑같이 시험했다.

| 항목 | mdtoc_s2 | fail_budget | mdtoc_claude_na | mdtoc_codex |
|---|---|---|---|---|
| 도움말 우선순위 4가지 | 같음 | 같음 | 같음 | 다름(2) |
| 4,301자리 수준 정수(Python 은 정수 자릿수 제한으로 2) | 다름(0) | 다름(0) | 다름(0) | 다름(0) |
| 없는 파일 이름에 LF | 같음 | 문구 다름(내용 비교 안 함) | 같음 | 문구 다름(내용 비교 안 함) |
| 없는 파일 이름에 잘못된 UTF-8 바이트 | 같음 | 문구 다름 | 문구 다름 | 문구 다름 |

- 4,301자리 정수는 모든 실행이 Python 과 달랐다. 이 차이를 찾아 노트에 적은 것은 Codex 뿐이다
- 오류 문구 차이(`(os error 2)` 덧붙임, U+FFFD 치환)는 계약 5절이 "내용은 비교 안 함"으로 둔 부분이다

## 3. 성능(같은 PC, rustify bench, hyperfine 10회)

| 케이스 | mdtoc_codex | mdtoc_claude_na |
|---|---|---|
| large-doc(19,437,698B) | Python 491.5ms / Rust 225.2ms, 2.18배 | Python 489.9ms / Rust 170.2ms, 2.88배 |
| large-doc-json | 2.68배 | 2.95배 |
| small-doc(63B) | 29.02배 | 31.1배 |

두 실행 모두 Cargo.toml 에 릴리스 최적화 설정이 없다. Codex 코드에 s1 과 같은 설정
(lto = true, codegen-units = 1, panic = "abort")만 더해 다시 재면 226.1ms → 218.3ms(±13.5)로
차이가 오차 범위 안이었다. 큰 입력의 시간 차이는 빌드 설정이 아니라 코드에서 나온다.
