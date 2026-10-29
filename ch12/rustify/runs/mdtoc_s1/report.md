# rustify 보고서: mdtoc (mdtoc_s1)

## 요약

| 항목 | 값 |
|---|---|
| 결과 | 통과 (멈춘 이유: gate_passed) |
| 엔진·모델 | claude · sonnet |
| 시작점 | 새로 이식 |
| 라운드 | 2 |
| 비용 | 2.53달러(추정) |
| 토큰 | input_tokens 142, cache_creation_input_tokens 172,818, cache_read_input_tokens 7,006,073, output_tokens 113,480 |
| 전체 시간 | 2486.6초 |
| 사람 개입 | 0회 |
| 확인 게이트(다른 시드) | 통과 |

## 라운드

| 라운드 | 단계 | 상태 | 턴 | 비용 | 게이트 |
|---|---|---|---|---|---|
| 1 | port | success | 82 | 1.82 | 통과 |
| 2 | followup | success | 20 | 0.27 | 통과 |

## 마지막 게이트

| 단계 | 결과 | 초 | 마지막 줄 |
|---|---|---|---|
| baseline | OK | 0.04 | baseline OK (25 files) |
| harness | OK | 0.0 |  |
| fmt | OK | 0.07 |  |
| clippy | OK | 0.07 |     Finished `dev` profile [unoptimized + debuginfo] target(s) in 0.03s |
| test | OK | 0.05 |      Running unittests src/main.rs (rust_app/target/debug/deps/mdtoc-4f1b5357358 |
| build | OK | 0.02 |     Finished `release` profile [optimized] target(s) in 0.00s |
| compare | OK | 0.9 | 31/31 cases match |
| fuzz | OK | 58.96 | 2000 random cases match (seed 557336115) |

게이트 격리(bubblewrap, 네트워크 없음): 예

## 성능

측정 환경: Ubuntu 24.04.5 LTS, Intel(R) Core(TM) i7-6700K CPU @ 4.00GHz, rustc 1.99.1 (58cf8f9c3 2026-10-13), Python 3.12.3, 릴리스 빌드, hyperfine 10회(워밍업 2회), 메모리는 5회 중앙값

| 케이스 | 입력 | Python 평균 | Rust 평균 | 배수 | Python 메모리 | Rust 메모리 |
|---|---|---|---|---|---|---|
| large-doc | 19,437,698B | 484.4ms | 143.8ms | 3.37 | 123.8MB | 29.4MB |
| large-doc-json | 19,437,698B | 499.6ms | 150.5ms | 3.32 | 123.8MB | 30.7MB |
| small-doc | 63B | 25.4ms | 0.8ms | 29.93 | 11.9MB | 1.9MB |

## 보안

- 정책 훅이 거부한 도구 호출: 7회
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
| 승인본(baseline.lock) SHA-256 | c66bb8d3d1432282f50c0647230bee891a537a5b75751ddd8c0208ab55daa169 |
| 실행 파일 SHA-256 | d6f112b7f6786006d5cdea8a1586f785ddc33dcbe474311fc5ae16626d920d47 |
| Cargo.lock SHA-256 | 9a449e4215765ce3732254c5f9b3ecd092046e33d8beb891f23dec4d71ca877c |
| 다시 빌드·검증(replay) | 시드 1527099461: 통과; 실행 파일 같음 |

## 에이전트가 확신하지 못한 부분(검증하지 않은 서술)

- Unicode 표는 소스에 고정되어 있다. 게이트 Python 이 3.12.3/unidata 15.0.0 이면 일치함을 확인했지만, 다른 버전이면 `\w`, `lower()`, `isspace()` 결과가 어긋날 수 있다(그 경우 `verify/gen_unicode_tables.py` 로 다시 만들고 exhaustive 로 확인).
- argparse 재현은 Python 3.12.3 소스 기준이다. 다른 3.12.x(예: 초기 릴리스)나 3.13 이상은 `-hx` 같은 가장자리 동작이 다를 수 있다. 이 환경에서는 다른 인터프리터를 찾아볼 수 없어(작업 폴더 밖은 읽을 수 없고 네트워크도 없다) 시험하지 못했다.
- 사용법 오류와 도움말의 stderr/stdout 내용은 계약상 비교 대상이 아니라 Python 과 문구를 맞추지 않았다(종료 코드와 비어 있음 여부만 맞춤). 계약과 기준 구현이 어긋난 곳은 아니다.
- 표준 입출력이 닫힌 경우와 쓰기 실패는 계약의 범위 밖이라 시험하지 않았고, 오류를 무시하고 지나간다.
- 입력은 전부 메모리에 올린다(계약의 범위 밖 조건과 동일).
