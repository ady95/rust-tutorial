# wordfreq Rust 이식: 구현 보고서

작성: 구현 단계 (2026-10-29). 기준: contracts/behavior_spec.md 2판, python_src/wordfreq.py, port/plan.json.

## 1. 구현 요약

- `rust_app/Cargo.toml`: package·bin 이름 `wordfreq`, edition 2021, 의존성 없음(std만). 산출물 `rust_app/target/release/wordfreq` (automation/port.json 의 binary 와 같음).
- `src/main.rs`: `fn main() -> ExitCode`. `args_os()` → `cli::parse` → 경로 정규화(`Path::components()` 로 다시 모으고 비면 `.`) → `fs::read` → `NotFound` 만 `file not found`, 그 밖의 io 오류는 `cannot read file`, 그 뒤 `String::from_utf8` 실패면 `not valid UTF-8` → tokenize → count → format → stdout `write_all`+`flush` 결과 확인(실패 시 `wordfreq: error: cannot write output`, 1). stderr 쓰기 결과는 무시. `print!/println!/eprintln!` 은 테스트 외 코드에 없음.
- `src/cli.rs`: argparse 3.12.3 `_parse_known_args`·`_parse_optional`·`_get_option_tuples`·`consume_optional`·`consume_positionals`·`_get_values` 를 표준 라이브러리 소스(/usr/lib/python3.12/argparse.py)를 읽고 그대로 옮긴 바이트 기반 파서. 지원: `--`(첫 번째만, 이후 전부 위치 인자, 위치 인자 값에서 첫 `--` 제거), `-` 위치 인자, `--top=1`, 긴 옵션 접두어 약어(`--to`, `--t=2`, `--js`, `--he`), 모호한 약어(`--=x`)는 분류 단계에서 즉시 오류, 반복 시 마지막 값(값마다 검증), 음수 모양 위치 인자(`^-\d+$|^-\d*\.\d+$`, `\d` 는 Python 의 Unicode Nd 64구간 표, `$` 는 끝의 `\n` 하나 앞에서도 맞음), 공백이 든 `-` 시작 인자는 위치 인자, `-h` 묶음(`-hh`, `-hfoo` 는 도움말 0, `-h-x`/`-h=x`/`--help=x` 는 2), 도움말은 Python 과 같은 바이트로 stdout 에 쓰고 0. positive_int 는 바이트 단위 `0`-`9` 검사 → 앞의 0 제거 → 18자리 초과면 `usize::MAX` → 아니면 직접 누적.
- `src/text.rs`: `PUNCTUATION`(38자), `is_py_space`(Python isspace 집합 하드코딩: U+0009–000D, U+001C–0020, U+0085, U+00A0, U+1680, U+2000–200A, U+2028, U+2029, U+202F, U+205F, U+3000), `py_lower`(글자별 `char::to_lowercase` + 예외 표 + CPython `handle_capital_sigma` 와 같은 Final_Sigma 판단), `tokenize`(자르기 → 문장 부호 제거 → 소문자 → 빈 문자열 버림), `count_words`(HashMap 집계, `(빈도 내림차순, 단어 바이트 오름차순)` 정렬, `truncate`).
- `src/output.rs`: 텍스트 형식, JSON 형식(키 순서 고정, `\" \\ \n \r \t \b \f` 짧은 이스케이프, 그 밖의 U+0000–001F 는 `\u00xx` 소문자 16진, U+007F·비ASCII 는 그대로).

### R2 (Unicode 버전) 처리: 전수 비교로 확정
- 환경: Python 3.12.3, `unicodedata.unidata_version` = 15.0.0. Rust `char::UNICODE_VERSION` = 17.0.0 (테스트 안에서 상수를 출력해 확인).
- `verify/gen_lower_table.py` 가 전 코드 포인트(서로게이트 제외)의 `chr(c).lower()` 와 Final_Sigma 분류를 `rust_app/tests/data/py_lower_table.txt` 로 만든다. Final_Sigma 분류(Cased / Case_Ignorable)는 Python 이 공개하지 않으므로 `(c+"Σ").lower()`, `("A"+c+"Σ").lower()` 결과로 유도했다(Rust 쪽도 같은 방법으로 관찰).
- 비교 결과(테스트 `dump_unicode_diffs` → `target/unicode_diffs.txt`):
  - 소문자 차이 55글자(9구간): Python 은 그대로 두고 Rust 만 바꾸는 글자. U+1C89, U+A7CB–A7CC, U+A7CE, U+A7D2, U+A7D4, U+A7DA, U+A7DC, U+10D50–10D65, U+16EA0–16EB8. 반대 방향(Python 은 바꾸는데 Rust 결과가 다른 것)은 0건.
  - Final_Sigma 분류 차이 196글자(40구간): 대부분 Rust 에서 새로 Cased/Case_Ignorable 이 된 글자. 특이 사항으로 U+0295 는 Python 에서 Cased, Rust 17.0 에서 Cased 아님. U+1171E 는 Python 에서 Case_Ignorable, Rust 에서 아님.
  - plan.json 이 예로 든 목록(U+10D50–10D65, U+A7CB·A7CC·A7DA·A7DC, U+1C89)은 일부만 맞았고, 실제로는 U+A7CE·A7D2·A7D4 와 U+16EA0–16EB8(Unicode 17.0) 이 더 있었다. 표는 추측 없이 비교 결과만으로 채웠다.
- 위 두 표를 `src/text.rs` 의 `PY_LOWER_UNCHANGED`, `PY_SIGMA_CLASS_OVERRIDES` 로 넣었고, 단위 테스트 `lower_table_matches_python`, `sigma_class_matches_python` 이 전 코드 포인트에서 차이 0 을 확인한다.

## 2. 실행한 명령과 결과

모든 명령은 작업 폴더 루트에서 실행했다.

| 명령 | 결과 |
|---|---|
| `python3 verify/env_info.py` | Python 3.12.3, unidata 15.0.0, euid 1000 (일반 사용자) |
| `python3 verify/gen_lower_table.py` | 1433 lower 매핑, 587 시그마 분류 구간 기록 |
| `python3 verify/gen_props.py` | 공백 10구간(plan 의 집합과 일치, `split()` 과 `isspace()` 결과 일치), `\d` 64구간 |
| `python3 verify/probe_cli.py --show` | Python 동작 관찰(아래 3절의 R12 등) |
| `python3 verify/probe_text.py` | 단위 테스트 기대값 계산 |
| 첫 `cargo test` (예외 표 비우고) | 3 실패: lower 55건 차이, sigma 196건 차이, `ΑΣ'Β` 기대값 불일치(아래 3절) — 예외 표를 확정하는 근거 |
| `cargo test -- --ignored dump_unicode_diffs` | 통과, 차이 목록 생성 |
| `cargo fmt --check` | 처음엔 서식 차이 → `cargo fmt` 적용 → 다시 `--check` 통과 |
| `cargo clippy --all-targets -- -D warnings` | 통과(경고 0) |
| `cargo build --release` | 통과 |
| `cargo test` (최종) | 단위 18 통과 / 1 ignored(차이 목록 생성 도구), 통합 8 통과, 실패 0 |
| `uv run python automation/compare.py --rust rust_app/target/release/wordfreq` | 22/22 cases match |
| `uv run python automation/scenarios.py --rust rust_app/target/release/wordfreq` | 15/15 scenarios match (closed-pipe, disk-full, permission-denied 포함) |
| `uv run python automation/fuzz.py --rust ... --examples 3000 --seed 20261029` | OK 3000 |
| 같은 명령 `--seed 7` | OK 3000 |
| 같은 명령 seed 없음 | OK 3000 |
| `python3 verify/probe_cli.py --rust rust_app/target/release/wordfreq` | 79/79 일치(도움말 바이트 일치 포함, R12 4건은 계약 값 2 로 판정) |
| `python3 verify/all_codepoints.py` | 32/32 조각 일치: 전 코드 포인트 × 5가지 문맥(`x{c}y`, `{c}`, `Α{c}Σ`, `ΑΣ{c}`, `{c}Σ`)을 실제 release 실행 파일에 넣어 텍스트·JSON 출력이 기준 구현 함수 결과와 바이트 단위로 같음 |

`uv run` 은 매번 `VIRTUAL_ENV=... does not match the project environment path .venv` 경고를 냈지만 결과에는 영향이 없었다.

rust_app 안에 둔 위험별 테스트:
- R1: `text::tests::r1_whitespace`, `space_table_matches_python`(전 코드 포인트)
- R2: `text::tests::r2_lowercase_and_sigma`, `lower_table_matches_python`, `sigma_class_matches_python`(전 코드 포인트)
- R4: `cli::tests::r4_argparse_syntax`, `r4_help`, `digit_table_matches_python`, 통합 `tests/cli.rs` 의 `r4_*`
- R5: `tests::r5_normalize_like_pathlib`, 통합 `r5_pathlib_normalization`
- R8: `output::tests::r8_json_escapes`
- R10: `text::tests::r10_bom_cr_nul`
- 그 밖: R3 `positive_int_rules`, R7 `r7_read_errors`, R9 `r9_disk_full_is_an_error`, R11 `r11_order_and_truncate`, R12 `r12_*`
- 기대값은 모두 verify/probe_cli.py, verify/probe_text.py 로 Python 을 실행한 출력에서 옮겼다.

## 3. 확인하지 못했거나 계약과 기준 구현이 다른 지점

1. **R12: 계약과 기준 구현이 다름 (계약을 따름).** UTF-8 이 아닌 바이트가 든 `--top` 값(`--top $'\xff'`, `--top=$'\xff'`), 모르는 옵션(`--$'\xff'`), 남는 위치 인자(`$'\xff'`)에서 기준 구현은 argparse 오류 메시지에 서로게이트가 들어가 stderr(strict UTF-8)에 쓰다가 `UnicodeEncodeError` 를 내고 **종료 코드 1** 로 끝난다(실행 확인. argparse `_print_message` 는 AttributeError/OSError 만 잡음). 계약 4절은 인자 오류를 2 로 정하므로 Rust 는 2 를 내고, 메시지는 U+FFFD 로 바꿔 쓴다. 이 경우를 다루는 공식 비교 도구는 없다.
2. **plan.json 의 R2 기대값 오류.** plan 은 `"ΑΣ'Β"` 의 결과를 `ας'β` 로 가정했지만 Python 실행 결과는 `ασ'β` 다(`'` 는 Case_Ignorable 이므로 건너뛰고 뒤의 `Β` 가 Cased). Python 결과를 테스트 기대값으로 썼다.
3. **예외 표는 툴체인에 묶임.** 예외 표는 이 환경의 Rust(Unicode 17.0.0)와 Python 3.12.3(15.0.0) 비교 결과다. 파이프라인이 다른 Rust 버전으로 빌드하면 표가 맞지 않을 수 있으며, 그 경우 `cargo test` 의 전수 비교 테스트가 실패해 드러난다. 툴체인 버전 자체는 `rustc --version`/`cargo --version` 이 허용 목록에 없어 거부되어 직접 보지 못했고, `char::UNICODE_VERSION` 만 확인했다.
4. **도움말(open question).** 계약에 없다. 기준 구현과 같은 문구·같은 바이트로 stdout 에 쓰고 0 으로 끝내게 했다(probe 로 바이트 일치 확인). 도움말을 쓰다가 stdout 이 실패하는 경우 기준 구현은 argparse 가 OSError 를 삼킨 뒤 인터프리터 종료 시 flush 실패로 120 이 될 수 있는데, Rust 는 0 이다. 실행으로 확인하지 않았다(계약 밖).
5. **빈 경로 `''`(open question).** 기준 구현대로 `.` 으로 바꿔 `cannot read file: `(1)로 처리했다. 계약의 "FILE 누락"(2)으로 봐야 하는지는 계약이 정하지 않았다.
6. **pathlib 정규화 차이(동작상 같음).** Python 은 `./a` 를 `a` 로, `//a` 를 `//a` 로 두고 Rust `components()` 는 `./a`, `/a` 로 만든다. Linux 에서 여는 파일은 같아 결과는 같다(`./tests//fixtures/basic.txt` 등 probe 로 확인). 메시지에는 항상 원래 인자를 쓴다.
7. **음수 판별 `\d` 집합**은 Python 3.12 의 Unicode 15.0 Nd 표를 하드코딩했다(전 코드 포인트 비교 테스트 있음). argparse 의 `$` 가 끝의 `\n` 하나 앞에서도 맞는 점(`-5\n` 은 위치 인자, `-5\n\n` 은 옵션)도 실행으로 확인해 따랐다.
8. **실행하지 못한 것.** `uv run pytest -q`(기준 구현의 tests/test_wordfreq.py)는 허용 목록에 없어 거부되었다. 우회하지 않았다. `python3 -c ...` 형태도 `;` 때문에 거부되어 verify/ 스크립트로 대신했다.
9. **Windows.** `cfg(not(unix))` 경로(표시 이름에 `to_string_lossy` 사용)는 작성만 했고 빌드·실행하지 않았다.
10. **권한 시나리오.** euid 1000 으로 실행했으므로 scenarios.py 의 permission-denied 는 의미 있는 결과다. 파이프라인이 root 로 다시 실행하면 그 시나리오는 의미가 없어진다(그래도 두 구현의 결과는 같게 나올 것).

## D1 수정

- 문제: 계약 5절 위반. 도움말(`-h`/`--help`) 출력 중 stdout 쓰기가 실패해도 0 으로 끝났다(위 4번 항목의 "Rust 는 0" 은 이제 사실이 아님).
- 수정: `src/main.rs` 의 `Outcome::Help` 처리에서 `write_stdout`(write_all+flush) 가 실패하면 `EXIT_HELP_WRITE_ERROR = 120` 을 돌려준다(기준 구현의 인터프리터 종료 시 flush 실패 코드와 같은 값). panic·매크로 출력 없음, stderr 메시지도 쓰지 않음(기준 구현의 stderr 는 비교 대상 아님). 성공 시 동작(0, 같은 바이트)은 그대로.
- 테스트: `tests/cli.rs` 에 `d1_help_write_failure_is_nonzero` 추가(`-h`, `--help`, `tests/fixtures/basic.txt -h` 를 stdout=/dev/full 로 실행해 종료 코드 120 확인).
- 확인: cargo fmt / clippy -D warnings / test(단위 18 통과·1 ignored, 통합 9 통과) / build --release 통과, compare.py 22/22, scenarios.py 15/15.
- 확인 못 함: `python3 verify/x_io_fs.py` 는 setup 에서 `verify/x_work_fs/locked` chmod 가 `Read-only file system`(이 역할은 verify/ 쓰기 불가)으로 실패해 D1 재현을 돌리지 못했다. 닫힌 파이프 경우는 통합 테스트로 직접 확인하지 않았다(/dev/full 만).
