# mdtoc Rust 이식 노트

port/plan.json 은 없었고, contracts/behavior_spec.md(2판)와 python_src/mdtoc.py 를 기준으로 구현했다. 표준 라이브러리만 쓴다.

## 1. 특별히 처리한 Python 동작

- **유니코드 표를 Python 3.12(Unicode 15.0)에서 생성** (`verify/gen_tables.py` → `rust_app/src/tables.rs`).
  Rust 표준 라이브러리는 유니코드 버전과 정의가 달라서 그대로 쓰지 않았다.
  - `\w`: Python `re` 로 코드 포인트 전체를 조사한 범위 표. Rust `is_alphanumeric` 은 결합 문자(Other_Alphabetic)를 단어 글자로 보지만 Python 은 아니다.
  - `str.lower()`: 한 글자→한 글자 매핑 표 + `İ`→`i̇`(두 글자) 특수 처리 + 끝 시그마(Σ→ς) 문맥. 시그마 문맥은 "cased 이면서 case-ignorable 이 아님"과 "case-ignorable" 두 집합을 Python 에서 탐침해 만든 표로 판정한다.
  - `Nd` 표: `int()` 가 받는 유니코드 숫자(예: `٣`)를 위해 쓴다.
- `str.strip()`: Python `isspace` 집합을 직접 나열(`\x1c`–`\x1f`, `\x85`, `\xa0`, U+2000–200A, U+2028/2029, U+202F/205F/3000 등).
- `str.splitlines()`: 10가지 줄 경계와 `\r\n` 을 직접 처리. 끝의 줄바꿈 뒤에는 빈 줄을 만들지 않는다.
- 제목 정규식 `HEADING`/`CLOSING`/`FENCE` 는 정규식 없이 같은 의미로 직접 구현(닫는 `#` 은 앞에 공백·탭이 있거나 문자열 전체가 `#` 일 때만 지움, `#` 7개 이상은 제목 아님, 공백 4칸 이상은 제목·코드 블록 시작 아님, 백틱 블록의 정보 문자열에 백틱이 있으면 시작 아님).
- 앵커 겹침 방지(3절 4번)와 수준 필터에 걸리는 제목도 번호를 소비하는 동작.
- `--json` 은 `json.dumps(ensure_ascii=False)` 형식(`, `/`: ` 구분자, 제어 문자 `\u00xx` 소문자 16진수, `\b \f \n \r \t` 는 짧은 표기).
- argparse 동작 모사: 약어 불가, `--opt=값`, 마지막 값 우선, `--` 이후는 위치 인자, 값 자리에 `-`/음수/공백 포함 문자열 허용, `int()` 규칙(공백, 부호, 밑줄, 유니코드 숫자), 위치 인자 2개 이상·알 수 없는 옵션은 종료 코드 2, 알 수 없는 옵션 뒤에 `--help` 가 오면 도움말(종료 코드 0), `-h` 로 시작하는 한 대시 인자는 도움말(Python 3.12.3 에서 확인한 동작).
- 입력 읽기 실패는 종료 코드 1, UTF-8 오류는 `mdtoc: error: <name>: not valid UTF-8`.

## 2. 직접 실행해 확인한 것

- `cargo fmt --check`, `cargo clippy --all-targets -- -D warnings`, `cargo test`(5개), `cargo build --release` 모두 통과.
- `compare_cli.py`: 36/36 일치.
- `fuzz_cli.py --examples 2000`: seed 12345, 987 둘 다 일치.
- `python3 verify/all_codepoints.py`: 서로게이트를 뺀 모든 코드 포인트(U+0000–U+10FFFF)를 10가지 문맥(제목 안 단독, 시그마 앞뒤, 닫는 `#` 근처, 코드 블록 정보 문자열 등)에 넣어 Python `mdtoc.build` 결과와 `--json` 출력을 비교해 전부 일치. 같은 스크립트가 인자 목록 약 45개의 종료 코드와 정상 출력을 Python 과 비교해 일치(도움말 본문은 비교 안 함).
- `python3 verify/gen_tables.py` 로 표를 다시 만들 수 있다(만든 뒤 `cargo fmt` 필요).

### 2차 확인 (3절 항목을 실행으로 확인)

- **argparse 조합**: `python3 verify/args_exhaustive.py` 가 29개 토큰(옵션, 값, `--`, `-h*`, 음수 모양, 공백 포함, 빈 문자열, 유니코드 숫자 등)의 길이 0~3 조합 27931개를 Python(`mdtoc.main` 을 프로세스 안에서 호출)과 비교한다. 종료 코드, 정상 출력, 종료 코드 2 일 때 stderr 가 비어 있지 않음이 전부 일치.
  - 이 비교로 실제 차이를 하나 찾아 고쳤다: `<위치 인자> <옵션> --` 순서(예: `- --json --`)에서 argparse 는 `--` 를 인식하지 못해 종료 코드 2 인데 Rust 는 정상 처리했다. 위치 인자 뒤에 옵션이 온 다음의 `--` 는 오류로 처리하도록 수정.
- **파일 읽기 오류**: `python3 verify/files_errors.py` — 없는 파일, 디렉터리, 권한 없음, 빈 이름, 너무 긴 이름, 심볼릭 링크 순환, 파일 아래 경로, `/dev/null` 에서 종료 코드·stdout·stderr 문장까지 Python 과 일치(계약상 stderr 는 비교 안 함인데도 같았다).
- **UTF-8 이 아닌 파일 이름**: 같은 스크립트에서 `\xff\xfe-name.md` 를 열어 보니 처음 구현(`to_string_lossy`)은 열지 못할 수 있었다. 인자 원본(`OsString`)으로 파일을 열도록 고쳤고, Python 과 같은 출력을 확인했다.
- **bench 사례**: `automation/gen_bench.py` 로 만든 입력으로 `python3 verify/bench_cases.py <폴더>` 실행. 3개 사례 모두 출력 동일(대용량 문서 기준 Python 0.52s, Rust 0.19s).
- **표 재현성**: 표를 만든 Python 과 비교에 쓴 Python 이 같은 3.12.3(Unicode 15.0)이고, 코드 포인트 전수 비교가 다시 전부 일치했다.
- 도움말 본문은 계약상 비교 안 함이며 Python 과 다르다(종료 코드 0 과 `usage` 로 시작함만 확인).
- 수정 후 완료 조건 재실행: fmt, clippy, test(5개), release 빌드, compare 36/36, fuzz 2000개(seed 424242) 통과.

## 3. 확신하지 못하는 부분

- 표는 Python 3.12.3 / Unicode 15.0 기준이다. 다른 유니코드 버전의 Python 에서는 결과가 달라질 수 있고, 이 환경에는 다른 버전이 없어 시험하지 못했다. 다른 버전이면 `verify/gen_tables.py` 로 표를 다시 만들어야 한다.
- plan.json 이 없어서 분석 단계 계획과의 차이는 확인하지 못했다.
- 인자 비교는 29개 토큰 풀의 길이 3 이하 조합이다. 더 긴 조합이나 풀 밖의 토큰은 전수 확인이 아니다.
- 계약과 기준 구현이 서로 다른 곳은 찾지 못했다(사람이 정할 일 없음).
