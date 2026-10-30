# rustify 보고서: mdtoc (mdtoc_claude_na)

## 요약

| 항목 | 값 |
|---|---|
| 결과 | 통과 (멈춘 이유: gate_passed) |
| 엔진·모델 | claude · sonnet |
| 시작점 | 새로 이식 |
| 라운드 | 2 |
| 비용 | 0.89달러(추정) |
| 토큰 | input_tokens 82, cache_creation_input_tokens 68,235, cache_read_input_tokens 2,001,516, output_tokens 41,669 |
| 전체 시간 | 930.3초 |
| 사람 개입 | 0회 |
| 확인 게이트(다른 시드) | 통과 |

## 라운드

| 라운드 | 단계 | 상태 | 턴 | 비용 | 게이트 |
|---|---|---|---|---|---|
| 1 | port | success | 36 | 0.56 | 통과 |
| 2 | followup | success | 35 | 0.33 | 통과 |

## 마지막 게이트

| 단계 | 결과 | 초 | 마지막 줄 |
|---|---|---|---|
| baseline | OK | 0.04 | baseline OK (25 files) |
| harness | OK | 0.0 |  |
| fmt | OK | 0.07 |  |
| clippy | OK | 0.07 |     Finished `dev` profile [unoptimized + debuginfo] target(s) in 0.03s |
| test | OK | 0.05 |      Running unittests src/main.rs (rust_app/target/debug/deps/mdtoc-4f1b5357358 |
| build | OK | 0.02 |     Finished `release` profile [optimized] target(s) in 0.00s |
| compare | OK | 1.03 | 36/36 cases match |
| fuzz | OK | 59.32 | 2000 random cases match (seed 466731092) |

게이트 격리(bubblewrap, 네트워크 없음): 예

## 성능

측정 환경: Ubuntu 24.04.5 LTS, Intel(R) Core(TM) i7-6700K CPU @ 4.00GHz, rustc 1.99.1 (58cf8f9c3 2026-10-13), Python 3.12.3, 릴리스 빌드, hyperfine 10회(워밍업 2회), 메모리는 5회 중앙값

| 케이스 | 입력 | Python 평균 | Rust 평균 | 배수 | Python 메모리 | Rust 메모리 |
|---|---|---|---|---|---|---|
| large-doc | 19,437,698B | 489.9ms | 170.2ms | 2.88 | 123.8MB | 35.2MB |
| large-doc-json | 19,437,698B | 508.8ms | 172.8ms | 2.95 | 123.8MB | 36.5MB |
| small-doc | 63B | 26.7ms | 0.9ms | 31.1 | 12.0MB | 2.1MB |

## 보안

- 정책 훅이 거부한 도구 호출: 4회
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
| codex | codex-cli 0.162.1 |
| rustc | rustc 1.99.1 (58cf8f9c3 2026-10-13) |
| cargo | cargo 1.99.1 (5f94df478 2026-08-27) |
| python | Python 3.12.3 |
| uv | uv 0.13.6 (x86_64-unknown-linux-gnu) |
| hyperfine | hyperfine 1.18.0 |
| 승인본(baseline.lock) SHA-256 | 718d8b8798d1f85b44b886c10dc403b9c3ec38fc7fabc9f021fe6fdcd58be3ee |
| 실행 파일 SHA-256 | 6aad1e8175704c94e680c3867af7c0500b2dfc94e915588175c64b2df81c76c9 |
| Cargo.lock SHA-256 | 9a449e4215765ce3732254c5f9b3ecd092046e33d8beb891f23dec4d71ca877c |
| 다시 빌드·검증(replay) | 시드 704102323: 통과; 실행 파일 같음 |

## 에이전트가 확신하지 못한 부분(검증하지 않은 서술)

- 표는 Python 3.12.3 / Unicode 15.0 기준이다. 다른 유니코드 버전의 Python 에서는 결과가 달라질 수 있고, 이 환경에는 다른 버전이 없어 시험하지 못했다. 다른 버전이면 `verify/gen_tables.py` 로 표를 다시 만들어야 한다.
- plan.json 이 없어서 분석 단계 계획과의 차이는 확인하지 못했다.
- 인자 비교는 29개 토큰 풀의 길이 3 이하 조합이다. 더 긴 조합이나 풀 밖의 토큰은 전수 확인이 아니다.
- 계약과 기준 구현이 서로 다른 곳은 찾지 못했다(사람이 정할 일 없음).

## 에이전트가 사람에게 넘긴 결정(검증하지 않은 서술)

(노트에 이 절이 없음)
