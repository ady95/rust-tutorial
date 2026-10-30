# rustify 보고서: mdtoc (fail_budget)

## 요약

| 항목 | 값 |
|---|---|
| 결과 | 통과 (멈춘 이유: gate_passed) |
| 엔진·모델 | claude · sonnet |
| 시작점 | 새로 이식 |
| 라운드 | 1 |
| 비용 | 0.51달러(추정) |
| 토큰 | input_tokens 54, cache_creation_input_tokens 41,144, cache_read_input_tokens 833,488, output_tokens 25,038 |
| 전체 시간 | 405.1초 |
| 사람 개입 | 0회 |
| 경고 | 마지막 세션이 끝나지 않음(error_max_budget_usd). 게이트 밖의 검증이 남았을 수 있음 |
| 확인 게이트(다른 시드) | 통과 |

## 라운드

| 라운드 | 단계 | 상태 | 턴 | 비용 | 게이트 |
|---|---|---|---|---|---|
| 1 | port | error_max_budget_usd | 38 | 0.51 | 통과 |

## 마지막 게이트

| 단계 | 결과 | 초 | 마지막 줄 |
|---|---|---|---|
| baseline | OK | 0.04 | baseline OK (25 files) |
| harness | OK | 0.0 |  |
| fmt | OK | 0.07 |  |
| clippy | OK | 0.2 |     Finished `dev` profile [unoptimized + debuginfo] target(s) in 0.15s |
| test | OK | 0.29 |      Running unittests src/main.rs (rust_app/target/debug/deps/mdtoc-4f1b5357358 |
| build | OK | 0.02 |     Finished `release` profile [optimized] target(s) in 0.00s |
| compare | OK | 1.06 | 36/36 cases match |
| fuzz | OK | 59.45 | 2000 random cases match (seed 404625990) |

게이트 격리(bubblewrap, 네트워크 없음): 예

## 보안

- 정책 훅이 거부한 도구 호출: 3회
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
| 실행 파일 SHA-256 | 77930590716e16ebab3df53dbac422ed1e796b1134853c6e8d2d8e4e1fc7f75f |
| Cargo.lock SHA-256 | 9a449e4215765ce3732254c5f9b3ecd092046e33d8beb891f23dec4d71ca877c |

## 에이전트가 확신하지 못한 부분(검증하지 않은 서술)

- **verify/all_codepoints.py 의 코드 포인트 비교가 자체 `lower()` 도입 후에도 실패합니다.** 원인은 확인하지 못했습니다. 이전 실패는 U+0897 등 유니코드 16 에서 추가된 글자 주변의 끝 시그마 차이였습니다. 새 표의 Case_Ignorable 판정 프로브(`"aΣ"+c`)나 Cased 프로브가 틀렸을 수 있습니다. verify/diff_codepoints.py 로 어느 글자가 다른지 확인하면 됩니다
- 자체 `lower()` 이후 compare/fuzz 결과는 미확인입니다. 자체 구현이 회귀를 만들었을 가능성이 있습니다
- 유니코드 표는 실행 환경의 Python 버전에 맞춰 생성했습니다. 다른 버전의 Python 이 기준이면 gen_tables.py 를 다시 실행해야 합니다

## 에이전트가 사람에게 넘긴 결정(검증하지 않은 서술)

(노트에 이 절이 없음)
