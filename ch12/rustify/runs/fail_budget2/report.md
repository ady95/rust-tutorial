# rustify 보고서: mdtoc (fail_budget2)

## 요약

| 항목 | 값 |
|---|---|
| 결과 | 실패 (멈춘 이유: budget) |
| 엔진·모델 | claude · sonnet |
| 시작점 | 새로 이식 |
| 라운드 | 1 |
| 비용 | 0.17달러(추정) |
| 토큰 | input_tokens 8, cache_creation_input_tokens 12,137, cache_read_input_tokens 42,463, output_tokens 4,885 |
| 전체 시간 | 72.1초 |
| 사람 개입 | 0회 |
| 확인 게이트(다른 시드) | - |

## 라운드

| 라운드 | 단계 | 상태 | 턴 | 비용 | 게이트 |
|---|---|---|---|---|---|
| 1 | port | error_max_budget_usd | 10 | 0.17 | 실패: fmt, clippy, test, build, compare, fuzz |

## 마지막 게이트

| 단계 | 결과 | 초 | 마지막 줄 |
|---|---|---|---|
| baseline | OK | 0.04 | baseline OK (25 files) |
| harness | OK | 0.0 |  |
| fmt | 실패 | 0.1 | Error writing files: failed to resolve mod `wordtab`: /home/dev/work/rustify_ws/ |
| clippy | 실패 | 0.49 | error: could not compile `mdtoc` (bin "mdtoc" test) due to 1 previous error |
| test | 실패 | 0.22 | error: could not compile `mdtoc` (bin "mdtoc" test) due to 1 previous error |
| build | 실패 | 0.08 | error: could not compile `mdtoc` (bin "mdtoc") due to 1 previous error |
| compare | 실패 | 0.0 | 빌드 실패로 실행하지 않음 |
| fuzz | 실패 | 0.0 | 빌드 실패로 실행하지 않음 |

게이트 격리(bubblewrap, 네트워크 없음): 예

## 보안

- 정책 훅이 거부한 도구 호출: 2회
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
| 실행 파일 SHA-256 | None |
| Cargo.lock SHA-256 | 9a449e4215765ce3732254c5f9b3ecd092046e33d8beb891f23dec4d71ca877c |
