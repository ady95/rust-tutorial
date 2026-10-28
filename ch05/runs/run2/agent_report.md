# wordfreq Rust 이식 보고서

대상: `python_src/wordfreq.py` → `rust_app/` (Rust edition 2024, 표준 라이브러리만)

- `rust_app/src/lib.rs`: 단어 자르기(`tokenize`), 소문자 변환(`to_lower`), 세기(`count_words`), 출력 형식(`format_text`, `format_json`), 인자 해석(`parse_args`). 파일·표준 입출력에 접근하지 않는다. 단위 테스트 포함
- `rust_app/src/main.rs`: 인자 → 파일 읽기 → 출력, 오류 메시지와 종료 코드(0/1/2)

## 완료 조건 결과

이 세션의 셸에서는 `cargo`를 실행할 수 없었다. PATH에 `cargo`가 없고, `~/.cargo/bin/cargo.exe`를 전체 경로로 부르는 명령은 허용 목록(`cargo *`)에 맞지 않아 승인 요청에서 막혔다. 그래서 1·2·3·5는 직접 실행하지 못했고, 종료(Stop) 훅이 대신 실행한다.

| # | 조건 | 결과 |
|---|---|---|
| 1 | `cargo build --release` | 직접 실행 못 함. Stop 훅이 검사(결과: `reports/stop_checks.jsonl`의 `build`) |
| 2 | `cargo fmt --check` | 직접 실행 못 함. 편집 훅의 `cargo fmt`는 오류 없이 끝났음(문법 오류가 없다는 뜻). Stop 훅이 `--check`로 검사 |
| 3 | `cargo clippy --all-targets -- -D warnings` | 직접 실행 못 함. Stop 훅이 검사 |
| 4 | `cargo test` | **실행 못 함.** 세션에서 cargo를 부를 수 없고 Stop 훅도 `cargo test`는 돌리지 않음 |
| 5 | `uv run python automation/compare.py` | 직접 실행 못 함(release 바이너리가 아직 없음). Stop 훅이 빌드 뒤 검사 |

통과 여부는 `reports/stop_checks.jsonl`의 마지막 줄(이 세션의 `results`)로 확인해야 한다. 이 보고서를 쓴 시점에는 어느 것도 "통과"로 확인하지 못했다.

## 직접 정한 가정

- **공백**: Python `str.split()`의 공백 = Rust `char::is_whitespace`(Unicode White_Space) + U+001C..U+001F. Python은 bidi 종류 WS/B/S 또는 Zs를 공백으로 보는데, 이 둘의 차이는 U+001C..U+001F뿐이다
- **문장 부호**: `char::is_ascii_punctuation`(ASCII 32자) + `“ ” ‘ ’ … ·`. 앞뒤에서만 뗀다(`trim_matches`)
- **소문자**: `str::to_lowercase`를 쓴다. 전체 매핑(`İ` → `i̇`)과 어말 시그마(`Σ` → `ς`) 판정 규칙이 CPython `str.lower()`와 같다
- **Unicode 버전 차이**: Rust 표준 라이브러리는 Unicode 16 이상을 따르고 기준 Python 3.12는 15.0이다. 15.0 이후에 생긴 대문자는 기준에서는 미할당 문자라 소문자로 바뀌지 않으므로 그대로 둔다. 대상: U+1C89..1C8A, U+A7CB..A7CF, U+A7D2, U+A7D4, U+A7DA..A7DC, Garay 블록 U+10D40..10D8F. 이 문자들은 `Σ` 어말형 판정에서도 대소문자와 무관한 문자로 본다
- **정렬**: 빈도 내림차순, 같으면 `String`의 바이트 순. UTF-8 바이트 순은 코드 포인트 순과 같다
- **JSON**: Python `json.dumps(ensure_ascii=False)`처럼 `"` `\` `\n` `\r` `\t` `\b` `\f`는 짧은 이스케이프, 나머지 U+0000..U+001F는 `\u00xx`(소문자 16진수), 그 밖(U+007F, 한글 등)은 그대로 쓴다
- **`--top`**: ASCII 숫자만 받는다(AGENTS.md). `+5`, ` 5`, `1_0`, 전각 숫자는 오류(종료 코드 2). 앞의 0은 허용(`05` = 5). usize를 넘는 큰 수는 Python처럼 받아들이고 usize::MAX로 본다(어차피 모든 단어 출력)
- **인자**: `--top N`, `--top=N`, `--json`, `--`, `-h`/`--help`를 받는다. `--top`이 여러 번이면 마지막 값. 옵션 이름 줄여 쓰기(`--to`)는 받지 않는다. 인자 오류는 stderr에 사용법 한 줄 + `wordfreq: error: ...` 한 줄, 종료 코드 2
- **파일 오류 분류**: `ErrorKind::NotFound` → "file not found", UTF-8 디코딩 실패 → "not valid UTF-8", 그 밖의 읽기 실패(디렉터리 등) → "cannot read file". 디렉터리는 Windows에서 PermissionDenied, Linux에서 IsADirectory로 오므로 둘 다 "cannot read file"이 된다
- **`<FILE>` 표시**: 사용자가 준 인자를 그대로(`OsString::to_string_lossy`) 쓴다
- **BOM**: Python `encoding="utf-8"`처럼 U+FEFF를 떼지 않는다(공백이 아니므로 첫 단어에 붙는다)
- **stdout 쓰기 실패**(파이프 끊김 등): 계약에 없으므로 종료 코드 1로 조용히 끝낸다

## 기준 구현 의심 사항

기준 파일은 고치지 않았다.

1. **Unicode 버전이 계약에 고정되어 있지 않다.** 계약 2절 4항은 "Python `str.lower()`와 같은 규칙"이라고만 한다. Python 버전이 바뀌면(3.13 = Unicode 15.1, 3.14 = 16.0) 같은 입력의 출력이 달라질 수 있다. 계약에 Unicode 버전을 적는 편이 낫다
2. **pathlib 경로 정규화.** `Path("")`는 `.`(현재 폴더)가 되어 "cannot read file"이 되고, `basic.txt/`처럼 끝에 `/`가 붙은 경로는 `basic.txt`로 읽힌다. 계약에 없는 부수 동작이라 Rust에서는 재현하지 않았다(Rust는 운영체제가 주는 오류를 그대로 분류)
3. **오류 메시지 인코딩.** Windows에서 짝 없는 서로게이트가 든 경로 인자는 Python이 stderr에 `backslashreplace`로 쓰고, Rust는 U+FFFD로 바꾼다. 계약 범위 밖의 극단적 경우
4. **쓰기 실패 처리 없음.** stdout이 닫힌 파이프면 Python은 `BrokenPipeError` 트레이스백을 낸다. 계약에 정의가 없다

## 하지 못한 것과 이유

- **`cargo test`를 실행하지 못했다.** 세션 셸에서 cargo를 부를 수 없고(PATH에 없음, 전체 경로 실행은 승인에서 막힘) Stop 훅은 테스트를 돌리지 않는다. `lib.rs`의 단위 테스트(13개)는 작성만 했다. PATH에 `~/.cargo/bin`을 넣거나 직접 `cd rust_app; cargo test`로 확인해야 한다
- **완료 조건 1·2·3·5를 직접 실행하지 못했다.** 위 표대로 Stop 훅 결과에 의존한다
- **전체 Unicode 대조를 하지 못했다.** 모든 코드 포인트로 만든 입력을 `compare.py --cases`로 Python과 비교하려 했으나, 입력 파일을 만들 도구(cargo 실행, Python 스크립트)를 쓸 수 없었다
- **Unicode 15.0 이후 문자의 대소문자 속성 목록이 불완전할 수 있다.** 소문자 매핑이 새로 생긴 문자는 위 목록으로 처리했지만, 15.0 이후 추가된 결합 문자(Case_Ignorable)나 소문자(Cased)가 `Σ` 바로 옆에 올 때의 어말형 판정은 목록에 없는 문자에 대해 Python과 다를 수 있다. 외부 크레이트를 쓸 수 없고 Unicode 데이터 파일을 받을 수도 없어(네트워크 금지) 기억에 의존한 목록이다
