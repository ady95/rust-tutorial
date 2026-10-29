# 이식 보고서: wordfreq (sonnet1)

이 보고서의 수치는 파이프라인 기록(sessions.jsonl, gate_*.json, audit.jsonl, heldout.json)에서 계산했다.
에이전트가 쓴 글은 마지막 절에 따로 붙였다.

## 결과

| 항목 | 값 |
|---|---|
| 모드 | single (계획 사용: True) |
| 종료 이유 | gate_passed |
| 라운드 | 2 / 최대 4 |
| 확인 게이트(다른 무작위 입력) | True |
| 추정 비용 | $1.2268 (상한 $10.0) |
| 실행 파일 | `artifacts/wordfreq` sha256 `11c4193fe27d6d2c…` |
| Rust 코드 | 6개 파일 1384줄 |

숨긴 평가: 6/6 일치

| 입력 | 결과 | 다른 코드 포인트 수 |
|---|---|---|
| shape A{c}B | 같음 | 0 |
| shape {c}Σ | 같음 | 0 |
| shape Σ{c} | 같음 | 0 |
| shape A{c}Σ | 같음 | 0 |
| u0295_sigma.txt | 같음 | - |
| new_letters.txt | 같음 | - |

계획의 위험 점검 입력: 20/20 일치

## 미검증 항목과 사람이 정할 일

에이전트 노트의 '확신하지 못하는 부분'을 그대로 옮겼다. 게이트와 숨긴 평가는 이 항목을 시험하지 않는다.

- **[사람이 정할 일] UTF-8 이 아닌 옵션·`--top` 값**(`non_utf8_options.py` 로 실행 확인): 계약 4절은 인자 오류를 종료 코드 2로 정하는데, 기준 구현은 다음에서 2가 아닌 1(traceback)로 끝난다.
  - `--top \xff`, `--top=\xff`, `--top 1\xff`: argparse 가 ArgumentTypeError 메시지를 stderr 로 쓰다 실패한다.
  - `--\xff`, `-\xff`, `--to\xff`, `\xff --top 1`(모르는 옵션 오류 메시지에 서로게이트가 들어감): `UnicodeEncodeError: 'utf-8' codec can't encode character '\udcff'`.
  - Rust 는 계약대로 2를 낸다. 계약과 기준 구현이 다르므로 고치지 않았다. 계약(2)이 맞으면 기준 구현의 결함이고, 기준 구현(1)이 정답이면 계약에 예외를 적고 Rust 를 맞춰야 한다. 같은 결과가 나온 입력은 `--json=\xff`(2), `\xff` 하나만 주기(1, 파일 없음), `-h\xff`(0), `--help=\xff`(2)이다.
- **Rust 툴체인 의존**: `is_lower_exception` 의 55글자 목록은 현재 툴체인(Unicode 16 이상으로 보임) 기준이다. 툴체인을 올려 Unicode 표가 더 새로워지면 새 대소문자 쌍이 생길 수 있고, 이를 막는 자동 테스트는 없다. 툴체인을 바꾸면 `python3 verify/lower_table.py` 를 다시 실행해야 한다. Final_Sigma 와 `\d` 표는 Python 에서 만든 표라 툴체인과 무관하다.
- **도움말 문구**: Python 과 바이트 단위로 같게 맞추지 않았다(계약이 다루지 않음). 종료 코드 0과 stdout 출력만 맞췄다.
- **Final_Sigma 표 생성 방식**: 표는 Python 의 동작에서 탐침해 만들었고 속성 데이터 파일과 직접 대조하지는 않았다. 위 8가지 모양의 전수 비교로 검증했다.

## 라운드별 기록

| 라운드 | 결과 | 턴 | 시간(초) | 비용 | 코드 변경 | 게이트 실패 단계 | fuzz seed |
|---|---|---|---|---|---|---|---|
| 1 | success | 58 | 279.7 | $0.7684 | True | 없음 | 1159745649 |
| 2 | success | 39 | 524.9 | $0.4584 | True | 없음 | 1504985473 |

## 도구 호출과 권한

도구 호출(메인 에이전트): Bash 50, Edit 21, Write 15, Read 8, Grep 1

| 역할 | 허용 | 거부 |
|---|---|---|
| implementer_v2 | 90 | 5 |

거부된 호출(처음 10건):

- implementer_v2 Bash `cargo --version` — implementer_v2: 허용 목록에 없는 명령입니다: cargo --version
- implementer_v2 Bash `python3 --version` — implementer_v2: 허용 목록에 없는 명령입니다: python3 --version
- implementer_v2 Bash `grep -n "short_help_ok\|after_dd\|Opt::Help, Some" rust_app/` — 파이프 뒤에는 읽기 전용 필터(head, tail, grep 등)만 쓸 수 있습니다: after_dd\
- implementer_v2 Bash `id -u` — implementer_v2: 허용 목록에 없는 명령입니다: id -u
- implementer_v2 Read `/proc/self/status` — implementer_v2: 작업 폴더 밖(/proc/self/status)은 읽을 수 없습니다

## 환경

| 항목 | 값 |
|---|---|
| claude_code | 2.1.299 |
| model | claude-sonnet-5-5 |
| rustc | rustc 1.99.1 (58cf8f9c3 2026-10-13) |
| cargo | cargo 1.99.1 (5f94df478 2026-08-27) |
| python | Python 3.12.3 |
| os | Linux 6.18.33.2-microsoft-standard-WSL2 |
| claude_agent_sdk | 0.2.174 |
| sha256(baseline.lock) | `fd86a51b2772bc53…` |
| sha256(port/plan.json) | `4a4ff894303eafd7…` |

## 에이전트의 마지막 응답 (검증하지 않은 서술)

"확신하지 못하는 부분"에 적었던 항목을 하나씩 실행해 확인했습니다. 두 건은 실제 불일치여서 `rust_app/` 을 고쳤고, 한 건은 계약과 기준 구현이 달라 고치지 않고 사람이 정할 일로 남겼습니다. 완료 조건은 다시 실행해 모두 통과했습니다.

- **Final_Sigma**
  - 모든 코드 포인트를 Σ 앞뒤에 놓은 8가지 모양, 약 890만 단어를 Python 과 비교했습니다. 처음에는 490개 단어가 달랐습니다. Rust 표준 라이브러리의 Cased/Case_Ignorable 판정이 Python 15.0 과 달랐기 때문입니다.
  - Σ 를 직접 처리하도록 바꿨습니다. Python 의 동작을 탐침해 만든 표(`verify/gen_tables.py` 가 `rust_app/src/py_tables.rs` 를 생성)를 씁니다. 지금은 차이가 0입니다.
- **음수 모양 인자의 `\d`**
  - Python 은 유니코드 숫자 680글자를 모두 받는데 Rust 는 ASCII 숫자만 봐서 2,729개 입력 중 2,680개가 달랐습니다.
  - 같은 생성 표로 고쳐 지금은 차이가 0입니다.
- **UTF-8 이 아닌 옵션과 `--top` 값**
  - 계약은 인자 오류를 종료 코드 2로 정하는데, 기준 구현은 `--top \xff` 와 `--\xff` 등에서 코드 1로 죽습니다(`UnicodeEncodeError` 등).
  - Rust 는 계약대로 2를 냅니다. 계약과 기준 구현 중 어느 쪽이 맞는지는 사람이 정해야 해서 고치지 않았습니다.
- **권한 시나리오**: 실행 사용자는 uid 1000 이고 mode 0 파일에서 `PermissionError` 가 나므로, 이 환경에서는 시나리오가 의미가 있고 통과했습니다.
- **통합 테스트**: `rust_app/tests/cli.rs` 를 추가해 경로 정규화와 읽기 오류 분류를 고정했습니다.

게이트 결과는 `cargo fmt --check`, `clippy -D warnings`, `cargo test`(단위 12개와 통합 3개), `cargo build --release` 통과입니다. `compare` 22/22, `scenarios` 15/15, `fuzz` 3000개(seed 20261029)도 통과했습니다.

남은 불확실성은 두 가지입니다. 55글자 소문자 예외 목록은 현재 툴체인 기준이라, 툴체인을 올리면 `verify/lower_table.py` 를 다시 실행해야 합니다. 도움말 문구는 계약에 없어 Python 과 맞추지 않았습니다. 확인한 항목은 `reports/port_notes.md` 3절에서 2절로 옮겼습니다.

## 에이전트가 쓴 노트 (검증하지 않은 서술)

# wordfreq Rust 이식 노트

구성: `rust_app/` (std만 사용, 외부 크레이트 없음). `src/main.rs`, `cli.rs`, `text.rs`, `output.rs`, `py_tables.rs`(생성 파일), `tests/cli.rs`.
`port/plan.json` 은 있었고 읽었다. 계약과 다른 곳은 없었다. plan 과 달라진 곳은 아래에 따로 적었다.
`py_tables.rs` 는 `python3 verify/gen_tables.py` 가 Python 3.12.3(Unicode 15.0.0)의 동작에서 뽑아 만든다. 직접 고치지 않는다.

## 1. 특별히 처리한 Python 동작

- **공백**: `str.split()` 의 집합(U+0009–000D, 001C–001F, 0020, 0085, 00A0, 1680, 2000–200A, 2028, 2029, 202F, 205F, 3000)을 `is_py_space` 로 하드코딩했다. `split_whitespace` 는 쓰지 않는다.
- **소문자**: 글자 단위로 `char::to_lowercase` 를 쓰되
  - Python 15.0 이 바꾸지 않는 55글자(U+1C89, A7CB, A7CC, A7CE, A7D2, A7D4, A7DA, A7DC, 10D50–10D65, 16EA0–16EB8)는 그대로 둔다.
  - Σ(U+03A3)는 직접 만든 Final_Sigma 로 처리한다. 앞뒤 문맥의 "건너뛰는 글자(Case_Ignorable)"와 "Cased 글자" 표는 Python 의 동작을 탐침해 만든 표(`SIGMA_IGNORABLE`, `SIGMA_CASED`)다. Rust 표준 라이브러리의 문맥 판정은 쓰지 않는다(아래 2절 참고).
- **argparse**(손으로 쓴 파서, `cli.rs`): `-` 는 위치 인자, `--` 뒤는 모두 위치 인자, `--top=N`, `--top` 반복 시 마지막 값(앞 값이 틀려도 오류), 접두어 약어(`--to`, `--js`), 음수 모양(`\d` 는 Unicode Nd 전체)이거나 공백이 든 `-` 시작 문자열은 위치 인자, 모르는 옵션과 남는 위치 인자는 끝에서 2, `--json=x` 는 오류, `-h`/`--help` 는 stdout 에 쓰고 0(뒤의 모르는 옵션보다 먼저 처리). `-hx`, `-hh` 는 도움말(0), `-h=x` 는 2. 3.12.3 에서 실제로 돌려 본 결과를 따랐다.
  - plan 과 다른 점: plan 은 `--top -- 5` 를 값으로 받는 것을 가정할 수 있었지만 3.12.3 은 2를 낸다. 실행 결과를 따라 2로 했다.
- **--top 숫자**: 바이트 단위로 ASCII 숫자만 받고, 앞의 0을 떼고, 0은 오류, 18자리 초과는 `usize::MAX`.
- **경로**: `Path::components()` 로 pathlib 처럼 정규화한다(끝의 `/`, `.` 조각 제거, 빈 문자열은 `.`). 오류 메시지에는 정규화 전 인자를 쓴다. `args_os()` 를 써서 UTF-8 이 아닌 인자에서도 panic 이 없다. 표시 이름은 `from_utf8_lossy`.
- **읽기 오류**: `fs::read` 와 `String::from_utf8` 를 나눠, NotFound 만 `file not found`, 그 밖은 `cannot read file`, 디코딩 실패는 `not valid UTF-8`. BOM 과 `\r` 은 건드리지 않는다.
- **출력**: 전체를 한 문자열로 만들어 `write_all` + `flush` 로 쓰고 실패하면 stderr 에 메시지를 쓰고 1. `println!` 계열은 쓰지 않는다. JSON 이스케이프와 키 순서는 `output.rs` 에서 Python `json.dumps(ensure_ascii=False)` 규칙대로 직접 구현했다.
- **정렬**: `(-count, word)`, 문자열 바이트 순서 = 코드 포인트 순서. 상위 N개는 `min(n, len)` 로 자른다.

## 2. 직접 실행해 확인한 것

게이트(마지막 실행 기준):
- `cargo fmt --check`, `cargo clippy --all-targets -- -D warnings`, `cargo test`(단위 12개 + 통합 3개), `cargo build --release` 통과.
- `automation/compare.py` 22/22, `automation/scenarios.py` 15/15, `automation/fuzz.py --examples 3000` 통과(seed 12345, 987, 20261029).

추가 확인(`verify/`):
- **단일 글자 소문자**(`lower_table.py`): 전 코드 포인트(서로게이트·공백·문장 부호 제외)에서 Python 과 같다(차이 0). 예외 목록 적용 전에는 55글자 차이가 났다.
- **Final_Sigma**(`sigma_context.py`): 모든 코드 포인트 c 에 대해 `cΣ`, `αΣc`, `αcΣ`, `αΣcα`, `ΣcΑ`, `ΑΣcΑ`, `ccΣ`, `αΣcc` 8가지 모양, 약 890만 단어를 Python 과 비교했고 최종 차이 0이다.
  - 이전 확인 항목의 결과: Rust 표준 라이브러리의 문맥 판정을 그대로 쓰면 490개 단어가 달랐다(예: U+0295 뒤의 Σ, U+1ACF–1AEB·U+0897·U+1171E 같은 새 Case_Ignorable, U+1C8A·A7CD·A7CF 같은 새 Cased 글자). 그래서 Python 동작에서 뽑은 표를 쓰는 방식으로 고쳤다.
  - 한계: 문맥 글자 사이에 건너뛰는 글자가 2개 이상 연속되는 경우는 `ccΣ`, `αΣcc` 로 일부만 본다. 탐침 표는 글자 단위 속성이라 연속 규칙은 구현 로직이 같다는 점에 기댄다.
- **음수 모양 인자의 `\d`**(`negative_number_args.py`): Python 정규식 `\d` 가 Unicode Nd 680글자와 정확히 같은지 확인했고, 모든 Nd 글자에 대해 `-N`, `-N.N`, `-.N`, `-N\n` 과 비숫자 변형 2,729개의 종료 코드가 Python 과 같다. 처음에는 2,680개가 달랐고(아랍 숫자 등을 ASCII 만 보던 탓) 고쳤다.
- **argparse·pathlib 경계 입력**(`edge_args.py`): 약 50개에서 종료 코드·stdout·stderr 가 Python 과 같다(인자 오류는 stderr 비어 있지 않음만, 도움말은 문구 비교 안 함).
- **경로 정규화·읽기 오류 분류**: `rust_app/tests/cli.rs` 통합 테스트로 고정했다(`basic.txt/`, `basic.txt/.`, `./basic.txt`, `nope.txt/`, `basic.txt/x`, `''`).
- **권한 시나리오**(`whoami.py`): 실행 사용자는 uid 1000 이고, mode 0 파일을 읽으면 PermissionError 가 난다. 따라서 permission-denied 시나리오는 이 환경에서 의미가 있고 통과했다. 파이프라인이 다른 사용자(root)로 실행하면 의미가 없어지는데, 그 경우 Python·Rust 모두 같은 결과이므로 불일치는 생기지 않는다.

## 3. 확신하지 못하는 부분 / 사람이 정할 일

- **[사람이 정할 일] UTF-8 이 아닌 옵션·`--top` 값**(`non_utf8_options.py` 로 실행 확인): 계약 4절은 인자 오류를 종료 코드 2로 정하는데, 기준 구현은 다음에서 2가 아닌 1(traceback)로 끝난다.
  - `--top \xff`, `--top=\xff`, `--top 1\xff`: argparse 가 ArgumentTypeError 메시지를 stderr 로 쓰다 실패한다.
  - `--\xff`, `-\xff`, `--to\xff`, `\xff --top 1`(모르는 옵션 오류 메시지에 서로게이트가 들어감): `UnicodeEncodeError: 'utf-8' codec can't encode character '\udcff'`.
  - Rust 는 계약대로 2를 낸다. 계약과 기준 구현이 다르므로 고치지 않았다. 계약(2)이 맞으면 기준 구현의 결함이고, 기준 구현(1)이 정답이면 계약에 예외를 적고 Rust 를 맞춰야 한다. 같은 결과가 나온 입력은 `--json=\xff`(2), `\xff` 하나만 주기(1, 파일 없음), `-h\xff`(0), `--help=\xff`(2)이다.
- **Rust 툴체인 의존**: `is_lower_exception` 의 55글자 목록은 현재 툴체인(Unicode 16 이상으로 보임) 기준이다. 툴체인을 올려 Unicode 표가 더 새로워지면 새 대소문자 쌍이 생길 수 있고, 이를 막는 자동 테스트는 없다. 툴체인을 바꾸면 `python3 verify/lower_table.py` 를 다시 실행해야 한다. Final_Sigma 와 `\d` 표는 Python 에서 만든 표라 툴체인과 무관하다.
- **도움말 문구**: Python 과 바이트 단위로 같게 맞추지 않았다(계약이 다루지 않음). 종료 코드 0과 stdout 출력만 맞췄다.
- **Final_Sigma 표 생성 방식**: 표는 Python 의 동작에서 탐침해 만들었고 속성 데이터 파일과 직접 대조하지는 않았다. 위 8가지 모양의 전수 비교로 검증했다.
