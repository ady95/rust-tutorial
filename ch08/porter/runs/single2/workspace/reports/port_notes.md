# wordfreq Rust 이식 노트

- 대상: `python_src/wordfreq.py` (2판) → `rust_app/` (바이너리 `wordfreq`, 외부 크레이트 없음)
- 기준: `contracts/behavior_spec.md` 2판, `port/plan.json`
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
   - 접두어 약어(`--to`, `--js`, `--t=2`). `--=x`는 모호한 옵션이라 2
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
- `python3 verify/compare_args.py`: 인자·경로 가장자리 경우 88개(위 2·3번 항목, 도움말 문구, BOM, 제어 문자, Final_Sigma 등). 84개는 기준 구현과 같고,
  나머지 4개는 아래 3-1의 의도한 차이로 확인했다

## 3. 확신하지 못하는 부분 / 기준 구현과 다른 점

1. **[기준 구현과 다름, 계약을 따름] 인자 오류 메시지에 UTF-8이 아닌 바이트가 들어가는 경우** (`--top $'\xff'`, `--$'\xff'`,
   `-$'\xff'`, 남는 위치 인자 `$'\xff'`). 기준 구현은 stderr를 `reconfigure(encoding="utf-8")`로 바꿔서 strict 모드가 된다.
   그래서 argparse가 오류 메시지를 쓸 때 `UnicodeEncodeError` traceback이 나고 **종료 코드 1**로 끝난다(실행해서 확인함).
   계약 4절은 인자 오류를 2로 정했으므로 Rust는 2와 usage 메시지(잘못된 바이트는 U+FFFD)를 낸다.
   plan.json의 R12 open question이 바로 이 경우다. 계약과 기준 구현 중 어느 쪽이 맞는지 사람이 결정해야 한다.
   자동 비교 도구(compare/scenarios/fuzz)는 이 경우를 시험하지 않는다.
2. **도움말 쓰기 실패**: 기준 구현은 `print_help`의 OSError를 무시하지만, 종료할 때 stdout을 flush하다가 다시 실패할 수 있다(종료 코드 120 가능성).
   Rust는 쓰기 실패를 무시하고 0으로 끝낸다. 실행해서 확인하지 않았다(계약에 없는 항목).
3. **도움말 줄바꿈**: argparse는 `COLUMNS`/터미널 너비에 따라 도움말을 다시 줄바꿈한다. Rust는 기본 너비(80) 기준의 고정 문구다.
   아주 좁은 터미널에서는 다를 수 있다(계약에 없는 항목).
4. **인자 오류 메시지 문구**: 계약상 비교하지 않는 항목이다. argparse 문구와 비슷하게 만들었지만 모든 경우에 같다고 확인하지는 않았다.
5. **permission-denied 시나리오**: 실행 사용자를 확인하려던 명령(`id -u`)이 샌드박스 허용 목록에 없어 확인하지 못했다.
   root로 실행했다면 이 시나리오는 의미 있는 검증이 아니다(통과는 했다).
6. **경로 정규화**: `//a`는 pathlib에서 `//a`로 남지만 Rust는 `/a`로 연다. Linux에서는 같은 파일이다.
   Windows 경로(드라이브, UNC)의 pathlib 대응은 확인하지 않았다(scenarios.py도 Linux 전용이다).
7. Unicode 표는 이 환경의 Python 3.12.3(Unicode 15.0.0)에서 생성했다. 기준 Python의 Unicode 버전이 바뀌면
   `python3 verify/gen_unicode_tables.py`로 다시 생성하고 `cargo fmt`를 실행해야 한다
   (이때 버전을 고정한 단위 테스트가 실패하므로 바뀐 것을 알 수 있다).
