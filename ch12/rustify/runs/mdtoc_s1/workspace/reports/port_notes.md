# mdtoc Rust 이식 노트

구현: `rust_app/` (std 만 사용, 외부 크레이트 0개). 실행 파일 `target/release/mdtoc`.
모듈: `cli.rs`(argparse 재현), `pystr.rs`(Python 문자열 동작), `headings.rs`(fence/제목), `slug.rs`, `render.rs`, `unicode_tables.rs`(생성 파일).

## 1. 특별히 처리한 Python 동작

- `str.splitlines()`: 줄 경계 10종(`\n \r \r\n \v \f \x1c \x1d \x1e \x85 U+2028 U+2029`)을 직접 구현. 끝 경계는 빈 줄을 만들지 않음.
- `str.strip()`: Rust `trim()` 대신 Python `isspace()` 표 사용(U+001C~001F 포함, U+FEFF 제외). 닫는 `#`, fence 닫기는 공백·탭 두 글자만 지우는 별도 함수.
- `re` 의 `\w`: `isalnum() or _` 의 범위 표. `lower()`: 전체 소문자 매핑 표(`İ` → 두 글자)와 Final_Sigma(Σ → ς/σ). 표는 `verify/gen_unicode_tables.py` 가 Python 3.12.3(unidata 15.0.0)에서 생성. Final_Sigma 의 Cased/Case_Ignorable 은 `lower()` 탐침(`'A'+c+'Σ'`, `'1'+c+'Σ'`)으로 분류.
- 정규식 CLOSING/HEADING/FENCE: 정규식 없이 같은 의미로 손으로 구현(백트래킹 결과를 분석해 반영).
- 앵커 중복: 기본 앵커별 횟수만 셈(만든 `-N` 이름은 넣지 않음), 걸러 낸 제목도 셈, 빈 앵커 허용.
- `json.dumps(ensure_ascii=False)`: 구분자 `, `/`: `, `\" \\ \b \f \n \r \t` 와 나머지 0x00~0x1f 만 `\u00xx`. DEL, `/`, U+2028 은 그대로.
- UTF-8: `std::str::from_utf8` 의 엄격 검사, BOM 유지. 파일 이름은 바이트로 다루고 stderr 에는 UTF-8 이 아닌 바이트를 `\udcXX`(backslashreplace)로 표기.
- 파일 읽기 오류: `io::Error` 문구에서 ` (os error N)` 을 떼 strerror 와 같게 함. 디렉터리는 read 단계의 EISDIR 로 같은 경로.
- argparse(Python 3.12.3 의 `/usr/lib/python3.12/argparse.py` 소스를 읽고 재현): 약어 금지, `--opt=값`, 마지막 값, `-`/`--` 처리, 위치 인자 `?` 의 소비 순서(`a --json b` 는 오류), 오류와 `-h` 는 만나는 순서대로(`--bogus -h` 는 0, `--min-level 9 -h` 는 2), `-hx`·`-hhx` 는 도움말(0), `-hh` 는 도움말, `-h=x` 는 2, 옵션 값 자리에는 `--` 가 올 수 없음, 음수 모양 인자(`-5`, `-.5`, 유니코드 숫자 포함)와 공백이 든 인자는 위치 인자.
- `int()`: 앞뒤 공백, 부호, 유니코드 십진 숫자, 밑줄(`0_3`), 선행 0 을 Python 과 같게 해석.

처음 계획(port/plan.json)이 추정했던 argparse 동작 중 `-hx`(오류가 아니라 0)와 `--min-level -- 3`(오류) 은 실제 실행으로 틀린 것을 확인해 소스대로 고쳤다.

## 2. 직접 실행해 확인한 것

모두 통과한 결과만 적는다.

- `cargo fmt --check`, `cargo clippy --all-targets -- -D warnings`, `cargo test`(16개), `cargo build --release`: 통과.
- `.rustify/compare_cli.py`: 31/31 일치.
- `.rustify/fuzz_cli.py`: seed 20261030 으로 2000건, seed 7 로 5000건 일치.
- `python3 verify/exhaustive_codepoints.py`: 0x0~0x10FFFF 전체(surrogate 제외)를 제목 안·앞뒤 공백·닫는 `#` 앞뒤·`#` 뒤 구분자·들여쓰기·Σ 맥락 12자리에 넣은 문서에서 `--json` 출력이 기준 구현과 바이트 단위로 일치. fence 닫는 줄 뒤 자리는 공백류 전체와 몇 글자로 확인.
- `python3 verify/args_diff.py --depth 4`: 인자 70125개(플랜 목록, `int()` 값 46종 × 두 옵션 × 두 형식, 16개 토큰의 길이 4 이하 조합 전부)에서 종료 코드, stdout, 오류 시 stderr 비어 있음 여부가 일치.
- `python3 verify/edge_docs.py`: 867건 일치(줄 경계 11종 조합, 닫는 `#`, fence, BOM, 잘못된 UTF-8 변형, 파일/디렉터리/없는 파일/빈 이름/`-` 이름의 파일/비ASCII 이름/UTF-8 이 아닌 이름, stderr 바이트 포함).
- `python3 verify/bench_check.py`: automation 의 large.md 로 large-doc, large-doc-json, small-doc 출력이 일치. 이 환경에서 Python 약 0.53초, Rust 약 0.16초.
- `python3 verify/env_check.py` 와 `uv run python verify/env_check.py` (2차 확인):
  - 게이트가 쓰는 `uv run python` 은 `.venv/bin/python` 이고 Python 3.12.3, unidata 15.0.0 이다. `python3`(`/usr/bin/python3`)도 같은 버전이다. `unicode_tables.rs` 첫 줄 주석의 버전과 일치한다.
  - 표 재현성: `uv run python verify/gen_unicode_tables.py` 로 표를 다시 만든 뒤 fmt/clippy/test/release 빌드, compare, fuzz(seed 424242, 2000건), 코드 포인트 전수 비교, `args_diff.py --depth 4`(70125개), `edge_docs.py`(867건)를 다시 돌려 모두 통과했다.
  - 읽기 권한 오류: 실행 사용자는 root 가 아니다(euid 1000). 권한 0 인 파일에서 Python 과 Rust 모두 종료 코드 1, stdout 비어 있음, `mdtoc: error: cannot read <경로>: Permission denied` 로 바이트 단위까지 같았다. 권한 오류 경로를 실제로 탄 것이다.
- 위 환경에서 root 가 아니고 Python 이 3.12.3 이라는 사실은 이 실행 환경의 값이다.

## 3. 확신하지 못하는 부분

- Unicode 표는 소스에 고정되어 있다. 게이트 Python 이 3.12.3/unidata 15.0.0 이면 일치함을 확인했지만, 다른 버전이면 `\w`, `lower()`, `isspace()` 결과가 어긋날 수 있다(그 경우 `verify/gen_unicode_tables.py` 로 다시 만들고 exhaustive 로 확인).
- argparse 재현은 Python 3.12.3 소스 기준이다. 다른 3.12.x(예: 초기 릴리스)나 3.13 이상은 `-hx` 같은 가장자리 동작이 다를 수 있다. 이 환경에서는 다른 인터프리터를 찾아볼 수 없어(작업 폴더 밖은 읽을 수 없고 네트워크도 없다) 시험하지 못했다.
- 사용법 오류와 도움말의 stderr/stdout 내용은 계약상 비교 대상이 아니라 Python 과 문구를 맞추지 않았다(종료 코드와 비어 있음 여부만 맞춤). 계약과 기준 구현이 어긋난 곳은 아니다.
- 표준 입출력이 닫힌 경우와 쓰기 실패는 계약의 범위 밖이라 시험하지 않았고, 오류를 무시하고 지나간다.
- 입력은 전부 메모리에 올린다(계약의 범위 밖 조건과 동일).

## 4. 사람이 정할 일

없음. 이번 확인에서 계약과 기준 구현이 서로 다른 곳은 발견하지 못했다.
