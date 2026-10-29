# wordfreq Rust 이식 노트

## 이번 변경 (2판 → 3판)

1. **옵션 약어 금지** (`allow_abbrev=False`): `src/cli.rs`의 `parse_optional`에서 `--`로 시작하는 인자는
   접두어 검색(`get_option_tuples`)을 건너뛴다. `--to`, `--js`, `--he`, `--t=2`는 모르는 옵션이라 2가 된다.
   단일 `-` 인자(`-hx` 등)는 argparse처럼 계속 검색한다. 부수 효과로 `-h --=x`는 모호한 옵션 오류가 아니라
   도움말(0)이 된다(기준 구현으로 확인). 단위 테스트 기대값을 이에 맞게 고쳤다.
2. **인자 오류 메시지의 UTF-8이 아닌 바이트**: 기준 구현이 `backslashreplace`로 바뀌어 이제 2로 끝난다.
   Rust는 원래 2를 냈으므로 코드 변경은 없다(아래 3-1 갱신).
3. 경로 정규화(`a/`, `a/.`, `''`), `--top` 반복 시 마지막 값, 도움말 문구 비교 안 함, 닫힌 표준 입출력 범위 밖은
   기존 구현이 이미 계약대로였다. 새 케이스(usage-abbrev, path-trailing-slash, top-last-wins)가 통과한다.

3판 후 직접 실행한 것: `cargo fmt --check`, `cargo clippy --all-targets -- -D warnings`, `cargo test`(16개),
`cargo build --release` 모두 통과. `automation/compare.py` 25/25, `automation/scenarios.py` 15/15,
`automation/fuzz.py --examples 3000 --seed 4242` OK. 새로 만든 `verify/argv_diff.py`(인자 조합 14424개를 기준 구현과
종료 코드·stdout 비교)는 모두 일치. `verify/compare_args.py`는 84/88이며 나머지 4개는 stderr 문구 차이뿐이다(종료 코드는 둘 다 2).
`.rustify/fuzz_cli.py`는 `strategies` 모듈을 찾지 못해(`ModuleNotFoundError`) 실행하지 못했다. 도구 쪽 문제로 보이며 수정하지 않았다.
`verify/check_all_codepoints.py`는 후속 확인에서 다시 실행해 모두 일치했다(아래 2절).

후속 확인(확신하지 못하는 부분 점검): `verify/open_items.py`로 실행해 확인했고, 그 결과 **도움말 쓰기 실패를 고쳤다**.
Rust는 `-h`의 stdout 쓰기가 실패해도 0으로 끝났지만(`/dev/full`), 기준 구현은 120으로 끝난다(닫힌 파이프도 120).
계약 5절(stdout 쓰기 실패는 0이 아니어야 함)과 기준 구현이 모두 0이 아님을 요구하므로, Rust는 `cannot write output`을 쓰고 1로 끝나게 했다
(`src/main.rs`). 종료 코드 값은 120과 다르지만 계약은 0이 아닌 것만 요구한다. 이후 완료 조건을 다시 실행해 모두 통과했다(seed 9137).

이하는 2판 때의 노트이며, 약어·인자 오류 항목은 위 내용이 우선한다.

- 대상: `python_src/wordfreq.py` (3판) → `rust_app/` (바이너리 `wordfreq`, 외부 크레이트 없음)
- 기준: `contracts/behavior_spec.md` 3판, `port/plan.json`
- 툴체인: rustc/cargo 1.99 (clippy 링크 기준), Unicode 16.x로 추정. 기준 Python: 3.12.3, Unicode 15.0.0
- 구성: `src/main.rs`(파일 읽기·오류·출력), `src/cli.rs`(argparse 호환 파서), `src/text.rs`(단어 규칙·집계),
  `src/output.rs`(텍스트/JSON), `src/unicode_tables.rs`(자동 생성 표)

## 1. 특별히 처리한 Python 동작

1. **Unicode 판단을 모두 Python에서 뽑은 표로 처리** (`verify/gen_unicode_tables.py` → `src/unicode_tables.rs`).
   Rust의 `to_lowercase`·`is_whitespace`는 쓰지 않는다. 그래서 툴체인의 Unicode 버전(16.x)과 관계없이 결과가 같다.
   - `str.lower()`: 한 글자 매핑 1432개(구간으로 압축)와 여러 글자 매핑 1개(U+0130 → `i̇`).
     Unicode 16.0에서 새로 생긴 대소문자 쌍(U+A7CB, U+10D50, U+1C89 등)은 Python처럼 그대로 둔다.
   - Final_Sigma: CPython `handle_capital_sigma`와 같은 알고리즘이다. 이 알고리즘이 쓰는 Case_Ignorable/Cased 분류는
     Python에서 직접 볼 수 없어서 `lower()` 결과로 역산했다(`"cΣ"`, `"AcΣ"`가 ς가 되는지로 판정).
     문맥은 문장 부호를 뗀 단어 안에서만 본다.
   - `str.split()`의 공백: `str.isspace()` 29자. U+001C–U+001F가 포함되고 U+200B·U+180E는 빠진다.
   - argparse 음수 판정 정규식의 `\d`: Unicode Nd 680자(`re`로 판정).
   - 생성 표의 Unicode 버전이 15.0.0인지 단위 테스트로 확인한다.
2. **argparse 3.12.3 동작을 그대로 옮김** (`/usr/lib/python3.12/argparse.py`의 `_parse_known_args`, `_parse_optional`,
   `_get_option_tuples`, `consume_optional`, `consume_positionals`, `_get_values`를 읽고 옮겼다)
   - 긴 옵션 약어는 받지 않는다(3판): `--to`, `--js`, `--t=2`, `--he`는 2. `--=x`는 모르는 옵션
   - `--top`을 여러 번 주면 마지막 값을 쓴다. 다만 각 값을 나올 때마다 검사하므로 `--top 0 --top 2`는 2
   - `--` 처리: 첫 `--` 뒤는 모두 위치 인자이고, 위치 인자 패턴은 `(-*A-*)`이다. 그래서 `x --`는 성공하지만
     `x --json --`는 `--`가 남는 인자가 되어 2이고, `-- --`는 파일 이름이 `--`가 된다
   - `-`, `''`, `-5`, `-.5`, `-5\n`(정규식 `$`), `-x y`(공백 포함)는 위치 인자이고 `-x.txt`는 모르는 옵션(2)이다
   - `-h`/`--help`/`--he`/`-hh`/`-hx`는 도움말을 stdout에 쓰고 0으로 끝난다. 도움말 문구도 바이트 단위로 같다(COLUMNS 기본값 기준).
     오류 처리 순서도 맞췄다. 모호한 옵션 → 왼쪽부터 처리하는 중의 오류/도움말 → 필수 인자 누락 → 남는 인자.
     예: `--bogus -h`는 0, `--top 0 -h`는 2, `-h=`는 2
   - `--top`: 바이트가 모두 ASCII 숫자인지 확인하고, 앞의 0을 뗀 뒤 18자리를 넘으면 `usize::MAX`로 둔다(`+3`, ` 3`, `٣`, `２`, `1_0`는 2)
3. **경로**: `pathlib.Path`처럼 `components()`로 다시 모은다(`a/`, `a/.`는 `a`가 되고 `''`는 `.`이 되어 `cannot read file: `).
   파일은 원래 바이트로 열고, 메시지의 이름은 원래 인자를 `from_utf8_lossy`로 바꾼다(최대 부분마다 U+FFFD).
4. **읽기 오류 분류**: `fs::read` 결과가 `NotFound`이면 file not found, 그 밖의 io 오류는 cannot read file이다.
   그 다음 `String::from_utf8`이 실패하면 not valid UTF-8이다. BOM을 떼지 않고 `\r`도 바꾸지 않는다(`\r`은 공백이라 결과가 같다).
5. **JSON**: `json.dumps(ensure_ascii=False, separators=(",", ":"))`의 이스케이프를 그대로 옮겼다.
   `\" \\ \n \r \t \b \f`, 그 밖의 U+0000–U+001F는 `\u00xx`(소문자)로 쓰고, U+007F와 비ASCII는 그대로 쓴다. 키 순서도 같다.
6. **정렬**: 빈도 내림차순 다음 `String`의 기본 순서(UTF-8 바이트 순 = 코드 포인트 순)로 정렬하고, `truncate(top)`으로 자른다.
7. **출력 실패**: `print!`/`eprintln!`을 쓰지 않는다. 출력 전체를 `write_all`과 `flush`로 쓰고, 실패하면
   `wordfreq: error: cannot write output`을 쓰고 1로 끝낸다. stderr 쓰기 결과는 무시하므로 panic하지 않는다.

## 2. 직접 실행해 확인한 것 (모두 통과)

- `cargo fmt --check`, `cargo clippy --all-targets -- -D warnings`, `cargo test`(단위 테스트 16개), `cargo build --release`
- `uv run python automation/compare.py --rust rust_app/target/release/wordfreq`: 22/22
- `uv run python automation/scenarios.py --rust ...`: 15/15 (closed-pipe, disk-full 포함)
- `uv run python automation/fuzz.py --rust ... --examples 3000 --seed N`: seed 20261029, 7, 98765에서 모두 OK
- `python3 verify/check_all_codepoints.py`: 서로게이트를 뺀 모든 코드 포인트를 확인했다. 글자마다 6가지 토큰
  (단독, 단어 가운데, Σ 앞뒤 문맥)을 만들어 평면 0–16 × 텍스트/JSON으로 기준 구현 CLI와 바이트 단위로 비교했고 모두 같았다
- `python3 verify/compare_args.py`: 인자·경로 가장자리 경우 88개. 84개는 기준 구현과 같고, 나머지 4개는 UTF-8이 아닌 바이트가 든
  인자 오류의 stderr 문구 차이뿐이다(둘 다 종료 코드 2, Python `\udcff` / Rust U+FFFD, 계약상 비교 안 함)
- 확신하지 못하던 항목을 실행으로 확인한 결과 (`python3 verify/open_items.py`, `python3 verify/argv_diff.py`):
  1. **UTF-8이 아닌 바이트가 든 인자 오류**: 3판 기준 구현도 2로 끝나 Rust와 일치(위 compare_args). 계약과 기준 구현의 불일치는 해소됐다.
  2. **도움말 쓰기 실패**: 위 "후속 확인"대로 `/dev/full`과 닫힌 파이프 모두 기준 구현 120, Rust 1(둘 다 0이 아님). 고쳤다.
  3. **도움말 줄바꿈**: `COLUMNS`=1–120을 모두 비교했다. 48–120은 바이트 단위로 같고, 1–47(좁은 터미널)은 다르다.
     계약이 도움말 문구를 비교하지 않으므로 고치지 않았다.
  4. **오류 메시지 문구**: 길이 1–3 인자 조합 14424개(`--top`, 약어, `--`, `-h`, 음수 모양 등)에서 도움말이 아닌 경우의
     종료 코드·stdout은 모두 같고, stderr(usage 포함)도 바이트 단위로 모두 같았다.
  5. **permission-denied**: 실행 사용자 euid 1000(root 아님)에서 chmod 000 파일로 직접 확인했다. 기준 구현·Rust 모두 `cannot read file`, 1, 같은 stderr.
  6. **경로 정규화**: 파일 하나에 대해 `//절대경로`, `///절대경로`, 끝의 `/`·`/.`·`//`, 중간 `./`를 시험했다. 종료 코드·stdout·stderr가 모두 같았다.
  7. **Unicode 버전**: `uv run python`이 쓰는 Python은 3.12.3, Unicode 15.0.0이고 표의 버전과 같다. 서로게이트를 뺀 모든 코드 포인트 비교도
     다시 실행해 평면 0–16 모두 일치했다.

## 3. 확신하지 못하는 부분 / 기준 구현과 다른 점

1. **도움말 줄바꿈(COLUMNS ≤ 47)**: Rust는 고정 문구라 매우 좁은 터미널에서 기준 구현과 다르다. 계약상 비교 안 함이므로 의도한 차이다.
2. **도움말 쓰기 실패의 종료 코드 값**: 기준 구현 120, Rust 1. 계약은 0이 아닌 것만 요구한다.
3. **Windows**: 경로 정규화(드라이브, UNC)와 `//a` 처리는 Linux에서만 확인했다. Windows에서는 실행해 보지 않았다.
4. **UTF-8이 아닌 인자 오류의 stderr 문구**: Python은 `\udcff`, Rust는 U+FFFD. 계약상 비교 안 함.
5. `.rustify/fuzz_cli.py`는 `strategies` 모듈이 없어 실행하지 못했다(도구 쪽 문제로 보임). 같은 역할의 `automation/fuzz.py`는 통과했다.
6. Unicode 표는 Python 3.12.3(Unicode 15.0.0)에서 생성했다. 기준 Python의 Unicode 버전이 바뀌면
   `python3 verify/gen_unicode_tables.py`로 다시 생성하고 `cargo fmt`를 실행해야 한다(버전을 고정한 단위 테스트가 실패해 알려 준다).

계약과 기준 구현이 서로 다른 항목은 현재 없다.
