# rustify 보고서: mdtoc (mdtoc_codex)

## 요약

| 항목 | 값 |
|---|---|
| 결과 | 통과 (멈춘 이유: gate_passed) |
| 엔진·모델 | codex · gpt-6.1-sol |
| 시작점 | 새로 이식 |
| 라운드 | 2 |
| 비용 | 구독 요금(토큰만 기록) |
| 토큰 | input_tokens 1,843,816, cached_input_tokens 1,789,568, cache_write_input_tokens 0, output_tokens 29,245, reasoning_output_tokens 6,308 |
| 전체 시간 | 691.7초 |
| 사람 개입 | 0회 |
| 확인 게이트(다른 시드) | 통과 |

## 라운드

| 라운드 | 단계 | 상태 | 턴 | 비용 | 게이트 |
|---|---|---|---|---|---|
| 1 | port | success | 1 | - | 통과 |
| 2 | followup | success | 1 | - | 통과 |

## 마지막 게이트

| 단계 | 결과 | 초 | 마지막 줄 |
|---|---|---|---|
| baseline | OK | 0.03 | baseline OK (25 files) |
| harness | OK | 0.0 |  |
| fmt | OK | 0.07 |  |
| clippy | OK | 0.07 |     Finished `dev` profile [unoptimized + debuginfo] target(s) in 0.03s |
| test | OK | 0.05 |      Running unittests src/main.rs (rust_app/target/debug/deps/mdtoc-4f1b5357358 |
| build | OK | 0.02 |     Finished `release` profile [optimized] target(s) in 0.00s |
| compare | OK | 1.05 | 36/36 cases match |
| fuzz | OK | 60.38 | 2000 random cases match (seed 1181947332) |

게이트 격리(bubblewrap, 네트워크 없음): 예

## 성능

측정 환경: Ubuntu 24.04.5 LTS, Intel(R) Core(TM) i7-6700K CPU @ 4.00GHz, rustc 1.99.1 (58cf8f9c3 2026-10-13), Python 3.12.3, 릴리스 빌드, hyperfine 10회(워밍업 2회), 메모리는 5회 중앙값

| 케이스 | 입력 | Python 평균 | Rust 평균 | 배수 | Python 메모리 | Rust 메모리 |
|---|---|---|---|---|---|---|
| large-doc | 19,437,698B | 491.5ms | 225.2ms | 2.18 | 123.8MB | 32.5MB |
| large-doc-json | 19,437,698B | 525.8ms | 196.2ms | 2.68 | 123.8MB | 43.6MB |
| small-doc | 63B | 26.3ms | 0.9ms | 29.02 | 12.0MB | 2.1MB |

## 보안

- 정책 훅이 거부한 도구 호출: 0회 (Codex 엔진은 훅이 없어 기록 없음)
- 산출물 비밀 검사: 5건
  - reports/closed_stdio_results.json: 홈 경로
  - reports/edge_results.json: 홈 경로
  - reports/edge_results_before.json: 홈 경로
  - reports/newline_filename_results.json: 홈 경로
  - verify/level_probe.rs: 홈 경로
- 기록하지 않은 큰 파일: 1개

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
| 실행 파일 SHA-256 | 1eabb466d832402ab8f9b2b518dfd0f53ec477b6f9af864be43e314ed47f3805 |
| Cargo.lock SHA-256 | 9a449e4215765ce3732254c5f9b3ecd092046e33d8beb891f23dec4d71ca877c |
| 다시 빌드·검증(replay) | 시드 2112511972: 통과; 실행 파일 같음 |

## 에이전트가 확신하지 못한 부분(검증하지 않은 서술)

(노트에 이 절이 없음)

## 에이전트가 사람에게 넘긴 결정(검증하지 않은 서술)

다음은 추측이나 미실행 항목이 아니라 실행으로 확인한 차이다. 사용자 지시에 따라 이 동작을 바꾸는 수정은 하지 않았다.

1. **긴 수준 정수**: 계약은 수준이 1~6인 정수라고만 정한다. 예를 들어 `--min-level`에 `0` 4,300개와 `1`을 붙인 4,301자리 문자열을 주면 수학적 값은 1이지만 Python은 기본 정수 자릿수 제한 때문에 오류 2로 거부한다. Rust는 값 1로 받아들인다. 밑줄은 숫자 자리 수에서 제외되며 Unicode 십진 숫자에서도 같은 차이가 재현되었다. 계약에 Python 자릿수 제한을 추가할지 사람이 결정해야 한다.
2. **도움말과 잘못된 인자의 우선순위**: Python은 `-hh`, `-hx`를 도움말 0으로 처리하며, `--js --help`처럼 알 수 없는 옵션 뒤의 도움말도 0으로 끝낸다. Rust는 알 수 없는 옵션 오류 2로 처리한다. 계약은 알 수 없는 옵션/약어는 오류 2, `-h`/`--help`는 0이라고 정하지만 이 결합의 우선순위나 `-h` 뒤 문자열 허용을 정하지 않는다. 추가 인자 오류보다 도움말이 우선하는 결합도 같은 분류다. 명령행 전수 검사에서 남은 차이 1,828개는 모두 Python 0/Rust 2인 이 부류이며 개별 인자는 JSON 증거에 있다.
3. **파일 이름에 LF가 있는 오류 메시지**: 계약 5절은 읽기 오류를 한 줄로 정하지만 Python은 파일 이름의 LF를 그대로 출력해 두 줄이 된다. Rust도 같은 이름 표시 동작을 유지한다. 파일 이름을 이스케이프할지, 한 줄 요구의 예외로 둘지 사람이 정해야 한다.

계약 범위 내에서 위에 나열한 충돌·우선순위 결정 외의 남은 관측 불일치는 없다. 임의 길이 문자/인자 조합 전체나 이 환경에 없는 Python 버전의 전수 검증을 완료했다는 의미는 아니다.
