# logstat Rust 이식 노트

- 대상: `python_src/logstat.py` → `rust_app/` (바이너리 `logstat`, 외부 크레이트 없음, std 만 사용)
- 기준: `contracts/behavior_spec.md`, 기준 구현, `port/plan.json`(계약과 충돌하는 부분은 없었음)
- 확인한 Python: 3.12.3 (`.venv`, `/usr/bin/python3` 모두 3.12.3). 이 환경에 다른 Python 버전은 없다

모듈: `cli.rs`(argparse 규칙), `help.rs`(argparse HelpFormatter, 터미널 폭), `csv.rs`(_csv.c 상태 기계), `json.rs`(json.loads 호환 파서),
`ts.rs`(fromisoformat + astimezone), `record.rs`(필드 규칙, 레코드 번호), `output.rs`(repr/.1f/JSON 이스케이프),
`lib.rs`(run, 집계, 출력), `main.rs`(파일·표준 출력). 검사용 `examples/pyprobe.rs`(verify/bulk_check.py 가 씀).

## 1. 특별히 처리한 Python 동작

CSV
- `_csv.c`(excel, strict=False)를 상태 단위로 그대로 옮겼다. StringIO(newline="")처럼 `\n`·`\r\n`·`\r` 에서 줄을 나누고 줄마다 EOL 을 넣는다.
  `"ab"cd`→`abcd`, `a"b` 그대로, 닫힌 인용 뒤 공백 유지, EOF 에서 안 닫힌 인용은 그때까지를 필드로, NUL 허용(3.12 실측).
- 빈 줄은 `[]` 행이고 헤더 자리에서도 건너뛰지 않는다. 그래서 `\n` 으로 시작하는 파일은 `missing column: ts`.
- 필드 한도: 글자(코드 포인트) 수가 131072 인 상태에서 한 글자를 더하면 오류. `""` 는 1자로 센다.
  파일 전체를 읽은 다음에 헤더·긴 필드 오류를 먼저 보므로 `--strict` 의 앞선 잘못된 레코드보다 우선한다.
- 같은 열 이름은 뒤의 열을 쓴다. 필드 수 비교는 중복을 포함한 헤더 길이와 한다.
- bytes 는 앞의 0을 떼고 13자리 이하일 때만 파싱, latency 는 `str::parse::<f64>`(정확한 반올림)로 1e9 와 비교.

JSON Lines
- `split('\n')` 만 쓰고, 건너뛰는 줄은 ` `·`\t`·`\r` 로만 이뤄진 줄뿐(`\f`, U+3000, U+00A0 줄은 레코드로 센다).
- 직접 만든 파서: BOM 시작 오류, 공백은 ` \t\n\r` 만, NaN/Infinity/-Infinity, 1e400→inf, 짝 없는 서로게이트 허용(WTF-8 로 보관),
  4300자리 초과 정수(부호 제외) 오류(무시되는 키 안에 있어도), 중첩 깊이 9997 초과 오류(최상위 배열도 `invalid json`).
  최상위 객체 멤버만 값으로 만들고 안쪽은 명시적 스택으로 문법만 검사한다(재귀·깊은 drop 없음).
- 중복 키는 뒤의 값. status/bytes 는 정수만(불리언·`200.0` 거부), latency 는 정수 또는 실수, NaN 거부, `-0.0` 은 부호 유지.

시각
- 오프셋 HH·MM 은 각각 범위 검사 없이 `h*60+m < 1440` 이면 유효(`+00:60`=+1h, `+00:99` 유효, `+23:60` 무효). 3.12.3 실측과 일치.
- 24시·60초·0년 거부, UTC 로 바꾼 결과가 1~9999년 밖이면 거부(`0001-01-01T00:00:00+00:01`, `9999-12-31T23:59:59-00:01`).
- isoformat 은 마이크로초가 0이 아닐 때만 `.ffffff`, 연도는 4자리 0 채움.

집계·출력
- bytes 합은 u128. 지연값 정렬은 안정 정렬(`sort_by` + `partial_cmp`)이라 `-0.0`/`0.0` 의 입력 순서를 지킨다.
- 경로는 WTF-8 바이트로 정렬(= 코드 포인트 순서, 서로게이트 포함).
- `repr(float)`: `{:e}` 의 최단 자릿수를 Python 규칙(decpt ≤ -4 또는 > 16 이면 지수, 지수 2자리 이상과 부호, `.0` 보장)으로 재배치.
  **이번에 고친 것**: 최단 자릿수의 두 후보가 정확히 같은 거리(동률)일 때 Rust `{:e}` 는 올림, Python 은 짝수를 고른다
  (예: 2^-25 → Python `2.9802322387695312e-08`, 고치기 전 Rust `...313e-08`). 같은 자릿수로 `{:.Ne}`(정확한 half-even)를 다시 만들어
  왕복하면 그것을 쓴다. 지연값 범위(0~1e9) 안에서도 생기는 차이였다(2^-25 등). 기존 게이트로는 드러나지 않았다.
- 오류율은 `errors as f64 / n as f64 * 100.0` 을 `{:.1}` 로(정확한 이진값 기준 half-even, rust-version 1.67 이상으로 명시).
- JSON 문자열 이스케이프는 `\" \\ \n \r \t \b \f`, 나머지 < 0x20 은 `\u00xx`(소문자), DEL·U+2028 은 그대로.

명령행(argparse 3.12 의 `_parse_optional`/`consume_optional`/`consume_positionals` 를 읽고 옮김)
- 정확한 이름만, `--top=3`, 반복 시 마지막 값(값마다 검증), 첫 `--` 뒤는 위치 인자, `-`·음수 모양(`\d` 는 Unicode 10진 숫자 표를 포함,
  끝의 `\n` 하나 허용)·공백 포함 문자열은 위치 인자, `-hX` 는 도움말, `-h=1`·`--json=1` 은 오류.
- 왼쪽부터 처리하며 값 오류는 즉시 종료 2, `-h`/`--help` 는 즉시 도움말(stdout, 종료 0), 알 수 없는 옵션·남는 인자·FILE 누락은 끝에서 종료 2.
- `--top` 은 ASCII 숫자만, 4300자리(앞의 0 포함) 초과는 오류, 값은 u64 로 포화.
- **이번에 고친 것: 도움말 폭.** 처음에는 80열 문구를 고정했는데, Python 은 `COLUMNS` 와 터미널 폭에 따라 39가지로 다른 출력을 낸다
  (verify/help_widths.py). `help.rs` 에 HelpFormatter(usage 줄바꿈, max_help_position, textwrap)를 옮기고,
  폭은 `shutil.get_terminal_size` 와 같게 정한다: `COLUMNS` 를 Python `int()` 규칙(유니코드 공백·10진 숫자, 밑줄, 부호, 4300자리 한도)으로
  해석해 양수면 그 값, 아니면 stdout(fd 1)에 `ioctl(TIOCGWINSZ)` 를 물어 0이 아니면 그 값, 그 밖에는 80.
- 판정 순서: 인자 → 형식 추론(바이트 끝을 ASCII 소문자로 비교; 이 접미사 글자로 소문자화되는 비ASCII 글자가 없음을 전체 코드 포인트로 확인)
  → 파일 읽기(`NotFound` 만 file not found, 디렉터리·ENOTDIR 등은 cannot read file) → UTF-8 엄격 해석(BOM 유지).
- 인자 오류의 stderr 문구는 80열 usage + 비슷한 메시지로 고정(계약 4절에서 비교 안 함).

## 2. 직접 실행해 확인한 것 (모두 이 세션에서 실행, 최종 코드 기준)

완료 조건
- `cargo fmt --check` 통과, `cargo clippy --all-targets -- -D warnings` 경고 없음, `cargo test` 25개 통과, `cargo build --release` 통과
- `automation/compare.py` 27/27, `automation/fuzz.py --examples 1500` 시드 77031·31415926 일치(수정 전에도 4개 시드 일치)

기존 게이트 밖의 비교(기준 구현과 Rust 를 같은 입력으로)
- `verify/extra_cases.py` 54/54(기준 구현 main 하위 프로세스 대 Rust 바이너리): R1~R15 경계 입력 전반(1차 보고의 53개 + repr 동률 후보 2,234개 값: 2^-1~2^-1074 와 i/2^j)
- `verify/probe.py`: 오프셋 `+00:60`·`+23:60`, 24시·윤초, CSV NUL, run() 깊이 9997/9998, `lower()` 매핑, .1f 동률

1차 보고의 "확신하지 못하는 부분"을 실행으로 확인한 결과
- **도움말 폭**(고침): `verify/bulk_check.py help` 로 폭 −500~3000 전부와 10^6·10^12·2^40(+5)의 `format_help()` 3,505가지가 바이트 단위로 일치.
  `verify/bulk_check.py int` 로 `COLUMNS` 해석(`int()`)을 모든 코드 포인트(서로게이트 제외) × 4가지 위치(`c`, `1c`, `c1`, `1c2`)와
  특수 문자열 33개, 합계 4,448,284개에서 일치. `verify/help_process.py` 로 실제 프로세스 98가지 일치:
  pipe 출력에서 `COLUMNS`(없음·빈 값·0·음수·문자·1·30~120·공백·밑줄·아라비아 숫자·비UTF-8 바이트·5000자리·20자리) × `LINES`(없음·24·0),
  pty 출력에서 터미널 폭 0·1·20·40·60·79·80·81·100·200·500 × `COLUMNS`(없음·0·45·x).
- **repr**(고침): `verify/bulk_check.py repr` 6,542,202개 비트 패턴 일치. 구성: 모든 유한 비트 패턴에서 무작위 300만, 0~1e9 비트 범위에서
  무작위 200만, 10의 거듭제곱 ±200 ulp, 2의 거듭제곱 ±20 ulp(서브노멀 포함), 0.000~100.000(소수 셋째 자리) 전부,
  동률이 몰리는 짧은 이진 소수 i/2^j 무작위 120만, 일부의 음수. 수정 전(당시 표본 558만 개)에는 813개가 달랐다(모두 최단 자릿수 동률).
- **오류율 .1f**: `verify/bulk_check.py rate` 로 n = 1~3000 의 모든 (errors, n) 조합 4,504,500개 일치.
- **비UTF-8 인자**: `verify/nonutf8_args.py` 1,536가지 일치(종료 코드·stdout; 오류면 stderr 가 비어 있지 않음).
  0x80~0xFF 모든 바이트를 존재/부재 파일 이름, 확장자 자리, `--`·`-` 옵션 이름, `-h` 뒤, `--format`·`--top` 값, `--top=` 값,
  공백 든 `-` 인자에 넣었다(Python 종료 코드 분포 0: 384, 1: 384, 2: 768).
- **JSON 깊이 9997**: `verify/depth_stack.py` 로 기준 구현을 실측. main 하위 프로세스(9997 허용, 9998 `invalid json`), 최상위 호출,
  Python 재귀 900단계 안, 스레드 안, Hypothesis `@given` 안(fuzz 와 같은 경로) 모두 9997 로 계약·Rust 와 같다.
  C 콜백 안에서 run() 을 부를 때만 달라진다(아래 3절).
- **서로게이트 경로 출력**: `extra_cases.py` 의 4가지(top 안·밖, --json, 정렬 위치)에서 종료 코드와 빈 stdout 이 Python 과 같고,
  top 밖이면 출력 전체가 같음을 확인. stderr(traceback)는 다르다(아래 3절, 사람이 정할 일).

## 3. 확신하지 못하는 부분 / 사람이 정할 일

- **계약에 없는 동작: 서로게이트 경로 출력.** JSON `"\ud800"` 같은 경로가 출력 대상(top_paths)에 들어가면 기준 구현은
  `sys.stdout.write` 에서 UnicodeEncodeError traceback 을 내고 종료 1(stdout 비어 있음)로 끝난다. Rust 는 종료 코드와 빈 stdout 은 맞추고
  stderr 에는 한 줄 메시지를 쓴다. traceback 은 Python 파일 경로·줄 번호를 담아 같게 만들 수 없다. 계약에 이 경우가 없으므로
  (a) 계약에 오류 메시지를 정해 넣을지, (b) 서로게이트를 다른 방식으로 다룰지는 사람이 정해야 한다. 고치지 않았다.
- **계약과 기준 구현이 다를 수 있는 경우: JSON 깊이 한도.** 계약은 9997 로 고정하지만, 기준 구현의 실제 한도는 C 재귀 카운터라서
  run() 을 C 콜백 안에서 부르면 줄어든다(`map()` 콜백 9995, `sorted(key=)` 콜백 9993). CLI 와 fuzz 경로는 9997 이라 지금 게이트와는 맞는다.
  Rust 는 계약대로 9997 이다. 어느 쪽을 기준으로 할지는 사람이 정할 일이며 고치지 않았다. 다른 3.12.x 빌드는 이 환경에 없어 재 보지 못했다.
- **확인하지 못한 것: Windows.** 이 환경에는 Windows 대상 std 가 없고(`cargo check --target x86_64-pc-windows-gnu` 가 E0463),
  네트워크가 없어 설치할 수 없다. Windows 에서는 터미널 폭 조회가 없어 `COLUMNS` 가 없으면 80을 쓰는데, Python 은 콘솔 폭을 물으므로
  콘솔에서 `-h` 출력이 다를 수 있다. 비UTF-8 경로 처리(`to_string_lossy`)와 파일 없음 분류도 Windows 에서는 확인하지 않았다.
  Linux 의 powerpc·mips·sparc 계열은 `TIOCGWINSZ` 값이 달라 터미널 폭 조회를 하지 않는다(역시 확인 못 함).
- **전수가 아닌 것**: repr 은 f64 전체(2^64)를 다 보지 못했다(위 6,542,202개 표본). 오류율은 n ≤ 3000 까지만 전수다(레코드 수는 상한이 없음).
- 인자 오류의 stderr 문구와 usage 는 argparse 와 같지 않다(계약 4절에서 비교 안 함, 고정 80열).
- 실행 환경에서 `VIRTUAL_ENV` 가 다른 경로를 가리킨다는 uv 경고가 나오지만 결과에는 영향이 없었다.
