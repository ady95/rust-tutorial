# rustify 보고서: wordfreq (wordfreq_v3)

## 요약

| 항목 | 값 |
|---|---|
| 결과 | 통과 (멈춘 이유: gate_passed) |
| 엔진·모델 | claude · sonnet |
| 시작점 | 이전 실행 /home/dev/work/ch08_ws/single2에서 증분 |
| 라운드 | 2 |
| 비용 | 0.59달러(추정) |
| 토큰 | input_tokens 68, cache_creation_input_tokens 61,250, cache_read_input_tokens 1,415,901, output_tokens 20,654 |
| 전체 시간 | 303.4초 |
| 사람 개입 | 0회 |
| 확인 게이트(다른 시드) | 통과 |

## 라운드

| 라운드 | 단계 | 상태 | 턴 | 비용 | 게이트 |
|---|---|---|---|---|---|
| 1 | update | success | 35 | 0.34 | 통과 |
| 2 | followup | success | 26 | 0.25 | 통과 |

## 마지막 게이트

| 단계 | 결과 | 초 | 마지막 줄 |
|---|---|---|---|
| baseline | OK | 0.03 | baseline OK (18 files) |
| harness | OK | 0.0 |  |
| fmt | OK | 0.06 |  |
| clippy | OK | 0.08 |     Finished `dev` profile [unoptimized + debuginfo] target(s) in 0.03s |
| test | OK | 0.05 |      Running unittests src/main.rs (rust_app/target/debug/deps/wordfreq-932b8064 |
| build | OK | 0.02 |     Finished `release` profile [optimized] target(s) in 0.00s |
| compare | OK | 1.13 | 25/25 cases match |
| scenarios | OK | 1.52 | 15/15 scenarios match |
| fuzz | OK | 5.21 | OK   3000 random inputs match |

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
| 승인본(baseline.lock) SHA-256 | 760e4b8d403c47f0b8a7e22052ec7c2affe7cc4a6dc365625368ba6dde2bd1c2 |
| 실행 파일 SHA-256 | 2359ef4bd52276f466fef9a2d3ff2f14dae81da2266cd24c6e92a043cf0d0d0c |
| Cargo.lock SHA-256 | ebfb6e53a79053e1fca5192cfc54141dd212c5fc106d452c039f8b294a19a3f9 |
| 다시 빌드·검증(replay) | 시드 2062053998: 통과; 실행 파일 같음 |

## 에이전트가 확신하지 못한 부분(검증하지 않은 서술)

1. **도움말 줄바꿈(COLUMNS ≤ 47)**: Rust는 고정 문구라 매우 좁은 터미널에서 기준 구현과 다르다. 계약상 비교 안 함이므로 의도한 차이다.
2. **도움말 쓰기 실패의 종료 코드 값**: 기준 구현 120, Rust 1. 계약은 0이 아닌 것만 요구한다.
3. **Windows**: 경로 정규화(드라이브, UNC)와 `//a` 처리는 Linux에서만 확인했다. Windows에서는 실행해 보지 않았다.
4. **UTF-8이 아닌 인자 오류의 stderr 문구**: Python은 `\udcff`, Rust는 U+FFFD. 계약상 비교 안 함.
5. `.rustify/fuzz_cli.py`는 `strategies` 모듈이 없어 실행하지 못했다(도구 쪽 문제로 보임). 같은 역할의 `automation/fuzz.py`는 통과했다.
6. Unicode 표는 Python 3.12.3(Unicode 15.0.0)에서 생성했다. 기준 Python의 Unicode 버전이 바뀌면
   `python3 verify/gen_unicode_tables.py`로 다시 생성하고 `cargo fmt`를 실행해야 한다(버전을 고정한 단위 테스트가 실패해 알려 준다).

계약과 기준 구현이 서로 다른 항목은 현재 없다.
