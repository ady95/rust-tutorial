# 이식 보고서: wordfreq (single1)

이 보고서의 수치는 파이프라인 기록(sessions.jsonl, gate_*.json, audit.jsonl, heldout.json)에서 계산했다.
에이전트가 쓴 글은 마지막 절에 따로 붙였다.

## 결과

| 항목 | 값 |
|---|---|
| 모드 | single (계획 사용: True) |
| 종료 이유 | gate_passed |
| 라운드 | 1 / 최대 4 |
| 확인 게이트(다른 무작위 입력) | True |
| 추정 비용 | $2.6720 (상한 $10.0) |
| 실행 파일 | `artifacts/wordfreq` sha256 `6b76a4104284ccb6…` |
| Rust 코드 | 5개 파일 1075줄 |

숨긴 평가: 2/6 일치

| 입력 | 결과 | 다른 코드 포인트 수 |
|---|---|---|
| shape A{c}B | 같음 | 0 |
| shape {c}Σ | 다름 | 1 |
| shape Σ{c} | 같음 | 0 |
| shape A{c}Σ | 다름 | 89 |
| u0295_sigma.txt | 다름 | - |
| new_letters.txt | 다름 | - |

계획의 위험 점검 입력: 20/20 일치

## 미검증 항목과 사람이 정할 일

에이전트 노트의 '확신하지 못하는 부분'을 그대로 옮겼다. 게이트와 숨긴 평가는 이 항목을 시험하지 않는다.

1. **소문자 예외 목록은 Python으로 전수 비교하지 못했습니다.** Python 실행은 허용 목록의 비교 도구로만 할 수 있어서, 표를 만드는 스크립트(`rust_app/tools/lower_table.py`)를 만들었지만 실행이 거부됐습니다. 삭제(`rm`)도 거부되어 파일이 그대로 남아 있습니다. 빌드에는 쓰이지 않습니다. 예외 목록은 Rust의 17.0 cased 범위와 제가 아는 15.0 범위를 비교해 정했으므로 다음 둘을 확인해야 합니다.
   - U+A7F1이 정말 15.0 이후에 추가된 글자인지
   - 15.0에서 17.0 사이에 기존 글자의 매핑이나 속성이 바뀐 곳이 없는지
   다음 단계에서 `uv run python rust_app/tools/lower_table.py OUT` 결과와 Rust 결과를 전수 비교할 것을 권합니다.
2. **15.0 이후 추가된 case-ignorable 글자(새 문자 체계의 결합 부호 등)는 처리하지 않았습니다.** `"AΣ<새 Mn>B"`처럼 새 결합 부호가 Σ와 cased 글자 사이에 끼면, Python은 `ς`를 내고 Rust는 `σ`를 낼 수 있습니다. 실행으로 확인하지는 않았습니다. fuzz가 이런 입력을 만들 확률은 매우 낮습니다.
3. **음수 판정용 `\d`(Nd) 표는 기억으로 작성했습니다**(Unicode 15.0, 68묶음). 틀린 묶음이 있으면 `-<그 숫자>` 인자의 처리가 갈립니다. Python에서는 위치 인자라 종료 코드 1이 되고, Rust에서는 모르는 옵션이라 2가 됩니다.
4. **도움말 문구**: argparse의 80칸 기본 형식을 손으로 옮겼고, Python 출력과 바이트 단위로 비교하지는 않았습니다. `COLUMNS`가 좁으면 Python은 줄을 바꾸지만 Rust는 바꾸지 않습니다. 계약에는 도움말 항목이 없습니다.
5. **UTF-8이 아닌 바이트가 든 인자의 인자 오류**(예: `--top $'\xff'`, `$'--\xff'`): 계획서 R12대로라면, 기준 구현은 stderr를 strict UTF-8로 다시 설정하기 때문에 오류 메시지를 쓰다 `UnicodeEncodeError`가 날 수 있습니다(그러면 종료 코드 1). Rust는 계약 4절을 따라 2를 냅니다. Python 쪽은 실행해 보지 못했습니다.
6. **argparse의 드문 경로는 소스를 읽고 옮겼을 뿐 Python과 직접 대조하지 못했습니다.** 해당하는 것은 `-hh=x`, `--json -- -x`, `--top 3 --`, `-- -- a.txt`, `-5\n` 같은 입력입니다. 기대값은 `rust_app/src/cli.rs`의 단위 테스트에 제가 추론한 값으로 들어 있습니다.
7. **Windows**(`cfg(not(unix))`)에서는 인자를 `to_string_lossy`로 다루며, 빌드도 실행도 확인하지 않았습니다.
8. **경로 정규화 차이**: Python pathlib은 맨 앞의 `//`를 그대로 두고, Rust components는 `/` 하나로 줄입니다. Linux에서는 같은 파일을 가리키므로 결과는 같다고 봤고, 실행해 확인하지는 않았습니다.

## 라운드별 기록

| 라운드 | 결과 | 턴 | 시간(초) | 비용 | 코드 변경 | 게이트 실패 단계 | fuzz seed |
|---|---|---|---|---|---|---|---|
| 1 | success | 49 | 569.3 | $2.6720 | True | 없음 | 993447470 |

## 도구 호출과 권한

도구 호출(메인 에이전트): Bash 21, Read 12, Write 9, Glob 2, Grep 2, Edit 2

| 역할 | 허용 | 거부 |
|---|---|---|
| implementer | 42 | 6 |

거부된 호출(처음 10건):

- implementer Bash `rustc --version` — implementer: 허용 목록에 없는 명령입니다: rustc --version
- implementer Bash `uv run python -c "import sys,unicodedata;print(sys.version, ` — 명령을 잇거나(; && ||) 파일로 쓰는(> <) 구문, 명령 치환은 허용하지 않습니다. 한 번에 명령 하나만 실행하세요
- implementer Bash `cargo --version --verbose` — implementer: 허용 목록에 없는 명령입니다: cargo --version --verbose
- implementer Bash `uv run python -c "import unicodedata, sys; print(sys.version` — 명령을 잇거나(; && ||) 파일로 쓰는(> <) 구문, 명령 치환은 허용하지 않습니다. 한 번에 명령 하나만 실행하세요
- implementer Bash `uv run python rust_app/tools/lower_table.py rust_app/tests/d` — implementer: 허용 목록에 없는 명령입니다: uv run python rust_app/tools/lower_table.py rust_app/tests/data/py312_lower.txt
- implementer Bash `rm rust_app/tools/lower_table.py` — implementer: 허용 목록에 없는 명령입니다: rm rust_app/tools/lower_table.py

## 환경

| 항목 | 값 |
|---|---|
| claude_code | 2.1.299 |
| model | claude-opus-5-5 |
| rustc | rustc 1.99.1 (58cf8f9c3 2026-10-13) |
| cargo | cargo 1.99.1 (5f94df478 2026-08-27) |
| python | Python 3.12.3 |
| os | Linux 6.18.33.2-microsoft-standard-WSL2 |
| claude_agent_sdk | 0.2.174 |
| sha256(baseline.lock) | `fd86a51b2772bc53…` |
| sha256(port/plan.json) | `4a4ff894303eafd7…` |

## 에이전트의 마지막 응답 (검증하지 않은 서술)

이식을 마쳤고, 완료 조건을 모두 직접 실행해 통과를 확인했습니다. 결과물은 `rust_app/`, 보고서는 `reports/port_notes.md`입니다.

**실행 결과**
- `cargo fmt --check`, `cargo clippy --all-targets -- -D warnings`, `cargo build --release`: 통과. clippy는 처음에 테스트 코드의 경고 1건으로 실패해서 고친 뒤 다시 돌렸습니다.
- `cargo test`: 18개 모두 통과(단위 13, 통합 5)
- `compare.py`: 22개 중 22개 일치
- `scenarios.py`: 15개 중 15개 일치. 권한 거부, 닫힌 파이프, 디스크 가득 참 상황도 포함됩니다.
- `fuzz.py`: 3000개씩 세 번(seed 없이 1번, seed를 바꿔 2번) 모두 일치

**주요 처리**
- 외부 크레이트 없이 표준 라이브러리만 썼습니다.
- Python의 공백 집합을 그대로 옮겼습니다. Rust 기본 함수는 U+001C–U+001F를 공백으로 보지 않기 때문입니다.
- 인자 해석은 시스템에 있는 Python 3.12.3의 argparse 소스를 읽고 처리 순서를 그대로 옮겼습니다. `--`, `-`, `--top=1`, `--top` 반복, `--to` 같은 약어, 음수 모양 인자, 도움말이 여기에 해당합니다.
- 경로는 Python처럼 정리합니다. 예를 들어 `basic.txt/`는 정상으로 읽힙니다.
- JSON 이스케이프는 직접 구현했고, 출력에 실패하면 멈추지 않고 종료 코드 1로 끝냅니다.
- 이 환경의 Rust는 Unicode 17.0, Python은 15.0입니다. 그래서 그 사이에 대소문자가 새로 생긴 글자는 소문자로 바꾸지 않는 예외로 두었습니다.

**확인하지 못한 부분** (자세한 내용은 보고서 3절)
1. 위 Unicode 예외 목록은 Python과 전 글자를 비교해 확정하지 못했습니다. Rust 쪽 출력과 제가 아는 15.0 범위를 대조해 정했습니다. 비교용 Python 표 생성 스크립트 `rust_app/tools/lower_table.py`는 만들었지만 실행이 허용되지 않았고, 삭제(`rm`)도 거부되어 그대로 남아 있습니다. 빌드에는 쓰이지 않습니다.
2. 음수 판정에 쓰는 Unicode 숫자 표와 도움말 문구는 기억과 소스를 보고 작성했고, Python 출력과 직접 비교하지 않았습니다.
3. argparse의 드문 경우(`-hh=x`, `--top 3 --` 등)는 소스를 읽고 기대값을 추론해 테스트에 넣었을 뿐, Python과 직접 대조하지 못했습니다.
4. UTF-8이 아닌 바이트가 든 인자로 인자 오류가 나면, Rust는 계약대로 종료 코드 2를 냅니다. 기준 구현은 오류 메시지를 쓰다 다른 오류가 나서 1을 낼 수 있지만, Python 쪽은 실행해 보지 못했습니다.

## 에이전트가 쓴 노트 (검증하지 않은 서술)

# wordfreq Rust 이식 노트

- 기준: `python_src/wordfreq.py`(2판), `contracts/behavior_spec.md`(2판), `port/plan.json`
- 결과물: `rust_app/`(패키지·바이너리 이름 `wordfreq`, 외부 크레이트 없음, edition 2021)
  - `src/main.rs`: 파일 읽기와 오류 분류, 출력, 종료 코드
  - `src/cli.rs`: argparse 호환 인자 파서, `positive_int`, `display_name`
  - `src/text.rs`: 공백 분리, 문장 부호 제거, 소문자 변환, 집계와 정렬
  - `src/output.rs`: 텍스트·JSON 형식(이스케이프 직접 구현)
  - `tests/cli.rs`: 실행 파일 통합 테스트
- 확인한 환경: Python 3.12.3(`/usr/bin`, venv) / Rust std `char::UNICODE_VERSION` = 17.0.0(clippy 메시지상 Rust 1.99.0)

## 1. 특별히 처리한 Python 동작

1. **공백 집합(`str.split()`)**: `char::is_whitespace` 대신 Python 3.12 `isspace` 집합을 하드코딩했습니다(U+0009–000D, U+001C–001F, U+0020, U+0085, U+00A0, U+1680, U+2000–200A, U+2028, U+2029, U+202F, U+205F, U+3000).
2. **문장 부호 제거**: 기준 구현과 같은 38자 집합으로 `trim_matches`를 씁니다. 처리 순서도 기준 구현과 같습니다(자르기 → 앞뒤 제거 → 소문자 → 빈 문자열 버리기).
3. **소문자 변환의 Unicode 버전 차이(15.0 대 17.0)**: `str::to_lowercase`(완전 매핑과 Final_Sigma 포함)를 쓰되, 15.0 이후에 들어온 cased 글자에서 단어를 끊고 그 글자는 바꾸지 않습니다. 대상은 U+1C89–1C8A, U+A7CB–A7CF, U+A7D2, U+A7D4, U+A7DA–A7DC, U+A7F1, U+10D50–10D65, U+10D70–10D85, U+16EA0–16EB8, U+16EBB–16ED3입니다. Python에게 이 글자들은 미할당 글자라서 cased도 case-ignorable도 아니므로, 여기서 끊으면 Final_Sigma 문맥도 Python과 같아집니다.
4. **`--top`**: 바이트 단위로 ASCII `0`–`9`만 받습니다. 앞의 0은 떼고, 0은 오류로 처리합니다. 18자리를 넘으면 `usize::MAX`로 둡니다(기준 구현은 `sys.maxsize`). `str::parse`는 `+3`을 받아 주므로 쓰지 않았습니다.
5. **argparse 3.12.3 문법**: `/usr/lib/python3.12/argparse.py`의 `_parse_optional`, `_get_option_tuples`, `consume_optional`, `consume_positionals`, `_get_values` 순서를 그대로 옮겼습니다. 구체적으로는 다음과 같습니다.
   - `--` 처리: 처음 나온 `--`만 구분자로 보고, 위치 인자에서는 지웁니다. `--top` 값 옆에 `--`가 붙으면 오류 2입니다.
   - `-` 하나는 위치 인자로 봅니다.
   - `--top=N`을 받고, `--top`을 여러 번 주면 값마다 검사한 뒤 마지막 값을 씁니다.
   - 접두어 약어(`--to`, `--t=2`, `--js`, `--h`)를 받습니다. `--=x`처럼 여러 옵션에 맞으면 ambiguous로 2입니다.
   - 음수 모양 인자(`^-\d+$|^-\d*\.\d+$`)는 위치 인자로 봅니다. `\d`는 Unicode 15.0 Nd 표를 쓰고, `$`가 끝의 `\n` 하나 앞에서도 맞는 동작까지 맞췄습니다. 공백이 든 `-` 시작 인자도 위치 인자입니다.
   - 그 밖의 `-` 시작 인자는 모르는 옵션으로 2입니다.
   - `-h`/`--help`/`-hx`는 stdout에 도움말을 쓰고 0, `-h=1`/`-h-x`/`--json=1`은 2입니다.
   - 도움말보다 앞에 나온 인자 오류가 먼저 처리되고, 분류 단계의 ambiguous 오류는 도움말보다 우선합니다.
6. **경로 정규화(pathlib)**: `Path::components()`로 다시 모아 끝의 `/`와 `.`을 지우고, 비면 `.`을 씁니다. 그래서 `basic.txt/`는 읽기에 성공하고 `''`는 `cannot read file: `가 됩니다. 오류 메시지에는 정규화 전 원래 인자를 씁니다.
7. **UTF-8이 아닌 argv**: `args_os()`로 받아 바이트 그대로 파일을 열고, 표시용 이름만 `String::from_utf8_lossy`로 만듭니다.
8. **읽기 오류 분류**: `fs::read` 뒤에 `String::from_utf8`로 따로 검증합니다. `ErrorKind::NotFound`만 `file not found`이고, 나머지 io 오류는 `cannot read file`입니다. BOM은 떼지 않고 `\r`도 변환하지 않습니다. `\r`은 공백이라 결과가 같습니다.
9. **JSON**: `ensure_ascii=False` 규칙을 그대로 따릅니다. `\" \\ \b \f \n \r \t`는 짧은 형식, 나머지 U+0000–001F는 소문자 `\u00xx`, U+007F와 비ASCII는 그대로 씁니다. 키 순서는 코드에 고정했습니다.
10. **출력 실패**: 출력을 한 번에 `write_all`과 `flush`로 쓰고 결과를 검사합니다. 실패하면 `wordfreq: error: cannot write output`을 쓰고 1로 끝냅니다. `print!`, `println!`, `eprintln!`은 쓰지 않았고, stderr 쓰기 실패는 무시합니다.

## 2. 직접 실행해 확인한 것 (모두 이 작업 중 실행, 결과 그대로)

- `cargo fmt --check`: 통과(출력 없음)
- `cargo clippy --all-targets -- -D warnings`: 처음에 `useless_vec` 1건이 나와 테스트 코드를 고쳤고, 다시 실행해 통과했습니다.
- `cargo test`: 단위 13개와 통합 5개, 모두 통과
- `cargo build --release`: 성공
- `automation/compare.py`: 22/22 일치
- `automation/scenarios.py`: 15/15 일치(permission-denied, closed-pipe, disk-full 포함)
- `automation/fuzz.py --examples 3000`: seed 없이 1회, `--seed 20261029`, `--seed 7`로 실행해 세 번 모두 3000개 일치
- Rust std의 Unicode 버전과 cased 글자 범위: 일회용 테스트로 출력해 확인한 뒤 그 코드는 지웠습니다. 위 3번 예외 목록은 이 출력과 Unicode 15.0 지식을 비교해 정했습니다.

## 3. 확신하지 못하는 부분

1. **소문자 예외 목록은 Python으로 전수 비교하지 못했습니다.** Python 실행은 허용 목록의 비교 도구로만 할 수 있어서, 표를 만드는 스크립트(`rust_app/tools/lower_table.py`)를 만들었지만 실행이 거부됐습니다. 삭제(`rm`)도 거부되어 파일이 그대로 남아 있습니다. 빌드에는 쓰이지 않습니다. 예외 목록은 Rust의 17.0 cased 범위와 제가 아는 15.0 범위를 비교해 정했으므로 다음 둘을 확인해야 합니다.
   - U+A7F1이 정말 15.0 이후에 추가된 글자인지
   - 15.0에서 17.0 사이에 기존 글자의 매핑이나 속성이 바뀐 곳이 없는지
   다음 단계에서 `uv run python rust_app/tools/lower_table.py OUT` 결과와 Rust 결과를 전수 비교할 것을 권합니다.
2. **15.0 이후 추가된 case-ignorable 글자(새 문자 체계의 결합 부호 등)는 처리하지 않았습니다.** `"AΣ<새 Mn>B"`처럼 새 결합 부호가 Σ와 cased 글자 사이에 끼면, Python은 `ς`를 내고 Rust는 `σ`를 낼 수 있습니다. 실행으로 확인하지는 않았습니다. fuzz가 이런 입력을 만들 확률은 매우 낮습니다.
3. **음수 판정용 `\d`(Nd) 표는 기억으로 작성했습니다**(Unicode 15.0, 68묶음). 틀린 묶음이 있으면 `-<그 숫자>` 인자의 처리가 갈립니다. Python에서는 위치 인자라 종료 코드 1이 되고, Rust에서는 모르는 옵션이라 2가 됩니다.
4. **도움말 문구**: argparse의 80칸 기본 형식을 손으로 옮겼고, Python 출력과 바이트 단위로 비교하지는 않았습니다. `COLUMNS`가 좁으면 Python은 줄을 바꾸지만 Rust는 바꾸지 않습니다. 계약에는 도움말 항목이 없습니다.
5. **UTF-8이 아닌 바이트가 든 인자의 인자 오류**(예: `--top $'\xff'`, `$'--\xff'`): 계획서 R12대로라면, 기준 구현은 stderr를 strict UTF-8로 다시 설정하기 때문에 오류 메시지를 쓰다 `UnicodeEncodeError`가 날 수 있습니다(그러면 종료 코드 1). Rust는 계약 4절을 따라 2를 냅니다. Python 쪽은 실행해 보지 못했습니다.
6. **argparse의 드문 경로는 소스를 읽고 옮겼을 뿐 Python과 직접 대조하지 못했습니다.** 해당하는 것은 `-hh=x`, `--json -- -x`, `--top 3 --`, `-- -- a.txt`, `-5\n` 같은 입력입니다. 기대값은 `rust_app/src/cli.rs`의 단위 테스트에 제가 추론한 값으로 들어 있습니다.
7. **Windows**(`cfg(not(unix))`)에서는 인자를 `to_string_lossy`로 다루며, 빌드도 실행도 확인하지 않았습니다.
8. **경로 정규화 차이**: Python pathlib은 맨 앞의 `//`를 그대로 두고, Rust components는 `/` 하나로 줄입니다. Linux에서는 같은 파일을 가리키므로 결과는 같다고 봤고, 실행해 확인하지는 않았습니다.
