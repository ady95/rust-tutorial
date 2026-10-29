# rustify 보고서: mdtoc (mdtoc_s2)

## 요약

| 항목 | 값 |
|---|---|
| 결과 | 통과 (멈춘 이유: gate_passed) |
| 엔진·모델 | claude · sonnet |
| 시작점 | 이전 실행 mdtoc_s1에서 증분 |
| 라운드 | 2 |
| 비용 | 0.60달러(추정) |
| 토큰 | input_tokens 40, cache_creation_input_tokens 43,963, cache_read_input_tokens 773,017, output_tokens 10,140 |
| 전체 시간 | 875.0초 |
| 사람 개입 | 0회 |
| 확인 게이트(다른 시드) | 통과 |

## 라운드

| 라운드 | 단계 | 상태 | 턴 | 비용 | 게이트 |
|---|---|---|---|---|---|
| 1 | update | success | 37 | 0.33 | 통과 |
| 2 | followup | success | 2 | 0.27 | 통과 |

## 마지막 게이트

| 단계 | 결과 | 초 | 마지막 줄 |
|---|---|---|---|
| baseline | OK | 0.04 | baseline OK (25 files) |
| harness | OK | 0.0 |  |
| fmt | OK | 0.05 |  |
| clippy | OK | 0.07 |     Finished `dev` profile [unoptimized + debuginfo] target(s) in 0.03s |
| test | OK | 0.05 |      Running unittests src/main.rs (rust_app/target/debug/deps/mdtoc-4f1b5357358 |
| build | OK | 0.02 |     Finished `release` profile [optimized] target(s) in 0.00s |
| compare | OK | 1.04 | 36/36 cases match |
| fuzz | OK | 59.22 | 2000 random cases match (seed 1044917993) |

게이트 격리(bubblewrap, 네트워크 없음): 예

## 성능

측정 환경: Ubuntu 24.04.5 LTS, Intel(R) Core(TM) i7-6700K CPU @ 4.00GHz, rustc 1.99.1 (58cf8f9c3 2026-10-13), Python 3.12.3, 릴리스 빌드, hyperfine 10회(워밍업 2회), 메모리는 5회 중앙값

| 케이스 | 입력 | Python 평균 | Rust 평균 | 배수 | Python 메모리 | Rust 메모리 |
|---|---|---|---|---|---|---|
| large-doc | 19,437,698B | 502.6ms | 166.4ms | 3.02 | 123.8MB | 32.9MB |
| large-doc-json | 19,437,698B | 538.6ms | 172.7ms | 3.12 | 123.8MB | 34.1MB |
| small-doc | 63B | 26.4ms | 0.8ms | 32.27 | 12.0MB | 1.9MB |

## 보안

- 정책 훅이 거부한 도구 호출: 5회
- 산출물 비밀 검사: 0건
- 기록하지 않은 큰 파일: 0개

## 재현 정보

| 항목 | 값 |
|---|---|
| os | Ubuntu 24.04.5 LTS |
| kernel | 6.18.33.2-microsoft-standard-WSL2 |
| cpu | Intel(R) Core(TM) i7-6700K CPU @ 4.00GHz |
| claude_code | 2.1.299 (Claude Code) |
| claude_agent_sdk | 0.2.174 |
| rustc | rustc 1.99.1 (58cf8f9c3 2026-10-13) |
| cargo | cargo 1.99.1 (5f94df478 2026-08-27) |
| python | Python 3.12.3 |
| uv | uv 0.13.6 (x86_64-unknown-linux-gnu) |
| hyperfine | hyperfine 1.18.0 |
| 승인본(baseline.lock) SHA-256 | 718d8b8798d1f85b44b886c10dc403b9c3ec38fc7fabc9f021fe6fdcd58be3ee |
| 실행 파일 SHA-256 | 5e1b1ca9f9c5898770dc1a1e606d0d0e01a8930bf64a2d37d278a061489e430c |
| Cargo.lock SHA-256 | 9a449e4215765ce3732254c5f9b3ecd092046e33d8beb891f23dec4d71ca877c |
| 다시 빌드·검증(replay) | 시드 1242573078: 통과; 실행 파일 같음 |

## 에이전트가 확신하지 못한 부분(검증하지 않은 서술)

- 다른 Python 버전(3.12.3 이 아닌 3.12.x, 3.13 이상)에서의 argparse/Unicode 동작: 이 환경에서는 다른 인터프리터를 쓸 수 없어(명령이 허용 목록으로 막히고 작업 폴더 밖은 읽을 수 없다) 시험하지 못했다. 아래 2절의 확인은 모두 3.12.3/unidata 15.0.0 기준이다.
- 도움말 내용은 계약상 비교 대상이 아니라 Python 과 문구를 맞추지 않았다(종료 코드와 비어 있음 여부만 맞춤). 계약과 기준 구현이 어긋난 곳은 아니다.
- 표준 입출력이 닫힌 경우와 쓰기 실패는 계약의 범위 밖이라 시험하지 않았고, 오류를 무시하고 지나간다.
- 입력은 전부 메모리에 올린다(계약의 범위 밖 조건과 동일).
