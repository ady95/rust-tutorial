# mdtoc Rust 이식 기록

## 1. 특별히 처리한 Python 동작

- 외부 크레이트 없이 Rust 표준 라이브러리만 사용했다. 실행 파일은 `rust_app/target/release/mdtoc`이다.
- `str.splitlines()`의 모든 줄 경계와 CRLF를 처리한다. BOM은 제거하지 않는다. CRLF를 나눌 때 생기는 빈 줄은 제목·펜스 상태에 영향을 주지 않는다.
- 코드 펜스의 문자·길이·정보 문자열 제한, ATX 제목의 들여쓰기와 구분자, 닫는 `#` 제거 및 Unicode `strip()`을 구현했다.
- Python 3.12.3 / Unicode 15.0.0에서 생성한 `\w`, 공백, 소문자 변환, Cased, Case_Ignorable, 십진 숫자 표를 포함했다. `İ`의 확장 소문자와 그리스어 `Σ`의 문맥별 최종 시그마를 처리한다. 생성 스크립트는 `verify/generate_unicode.py`이다.
- 앵커의 기본 문자열별 번호와 이미 사용한 전체 앵커 집합을 함께 관리한다. 수준 필터로 제외한 제목도 번호에 반영한다.
- 번호 목록의 깊이별 카운터와 하위 깊이 초기화, JSON 우선순위, Python JSON의 구분자 및 제어 문자 이스케이프를 구현했다.
- 옵션 중복의 마지막 값, `--option=value`, `--`, 옵션 약어 거부, Unicode 숫자를 포함한 수준 정수, UTF-8 오류 및 읽기 오류의 종료 코드를 처리한다.
- `port/plan.json`은 존재하지 않았다. 계약과 기준 구현을 사용했다.

## 2. 직접 실행해 확인한 것

다음 명령은 저장소 루트에서 실행했다.

- `cargo fmt --check --manifest-path rust_app/Cargo.toml`: 통과.
- `cargo clippy --manifest-path rust_app/Cargo.toml --all-targets -- -D warnings`: 통과.
- `cargo test --manifest-path rust_app/Cargo.toml`: 통과. Rust 단위 테스트는 0개이며 실제 동작은 아래 차등 검증으로 확인했다.
- `cargo build --release --manifest-path rust_app/Cargo.toml`: 통과.
- `env UV_CACHE_DIR=/tmp/mdtoc-uv-cache uv run python .rustify/compare_cli.py --rust rust_app/target/release/mdtoc`: 36/36 일치. 최종 빌드에서도 재실행했다.
- `env UV_CACHE_DIR=/tmp/mdtoc-uv-cache uv run python .rustify/fuzz_cli.py --rust rust_app/target/release/mdtoc --examples 2000 --seed 421803`: 2,000개 일치.
- 최종 빌드에서 `env UV_CACHE_DIR=/tmp/mdtoc-uv-cache PYTHONDONTWRITEBYTECODE=1 uv run python .rustify/fuzz_cli.py --rust rust_app/target/release/mdtoc --examples 2000 --seed 20261030`: 추가 2,000개 일치.
- `python3 verify/check_unicode.py`: Unicode 스칼라 값 1,112,064개를 포함한 제목들을 기준 구현과 JSON으로 대조했다. 각 문자 자체의 소문자·단어 문자 판정뿐 아니라 시그마 앞뒤 문맥, 공백·줄 경계·제목 해석도 대조했다. Unicode 정수와 잘못된 수준 인자 검사도 통과했다. 초기 정수 검사에서 발견한 U+001C 공백 차이를 수정하고 전체 검사를 다시 통과했다.

`uv` 기본 캐시는 읽기 전용이므로 `/tmp` 캐시를 지정했다. 보호된 소스·계약·테스트·하네스 파일의 내용은 수정하지 않았다.

### 미확인 항목의 추가 실행 결과

- UTF-8이 아닌 Unix 파일 이름에서 발견한 Rust 인자 변환 패닉을 수정했다. `args_os()`로 경로 바이트를 보존하고, 오류 표시에는 Python surrogateescape/backslashreplace 방식의 `\udcXX`를 사용한다.
- `python3 verify/check_raw_paths.py`: 777개 일치. NUL·슬래시를 제외한 단일 파일 이름 바이트 254종 전부 및 잘못된 UTF-8 바이트열 5종에 대해 정상 읽기, UTF-8 오류, 파일 부재를 검사했다. UTF-8 오류 메시지는 stderr 바이트까지 일치한다. 읽기 오류는 계약에 정한 접두사·종료 코드를 확인했다.
- `python3 verify/check_edges.py`: 토큰 20종의 길이 0~3 명령행 8,421개를 전수 실행했다. Python argparse와 차이가 난 1,828개는 모두 아래 3절의 도움말/오류 우선순위 문제다. 그 밖의 6,593개는 일치했다. 파일 뒤 옵션 뒤의 `--` 처리와 공백이 포함된 `- ` 파일 이름 해석 차이는 수정했다.
- 같은 스크립트의 원시 바이트 인자·파일 이름 검사 1,016개는 모두 일치한다. 도움말 내용은 계약에 따라 비교하지 않았다. 긴 정수 60개 중 42개는 일치하며, 차이 18개는 아래의 Python 4,300자리 제한뿐이다. 숫자 길이 1, 2, 639, 640, 641, 4,299, 4,300, 4,301, 5,000, 10,000, ASCII/아라비아/전각 숫자와 밑줄 구분자를 조합했다. 상세 결과는 `reports/edge_results.json`, 수정 전 결과는 `reports/edge_results_before.json`이다. 허용한 계약 충돌 외의 차이는 스크립트 assertion으로 실패한다.
- `python3 verify/check_level_scalars.py`: 실제 Rust 정수 파서를 별도 probe로 컴파일해 Unicode 스칼라 1,112,064개 전부를 단독 및 `문자 + 1 + 문자`로 검사했다. Python `int()`와 범위 판정의 결과 2,224,128개 전부가 일치한다. probe 소스와 실행 파일은 `verify/`에 생성한다.
- `python3 verify/check_sequences.py`: 경계 문자 8종으로 만든 길이 0~6 문자열 299,593개 전부를 순서 있는 문서로 검사했다. Cased/Case_Ignorable의 네 조합, 시그마, 확장 소문자를 대표하는 6종으로 만든 길이 0~5 문맥 9,331개 전부도 일치했다. 임의 길이 문자열 공간은 무한하므로 전수 완료라고 주장하지 않는다.
- 최종 코드에서 `python3 verify/check_unicode.py`를 다시 실행했다. 전체 Unicode 스칼라 1,112,064개 및 정수 경계 검사가 통과했다.
- 다른 Python 버전 여부를 실행 확인했다. `/usr/bin/python3`, `/usr/bin/python3.12`, 가상환경 Python은 모두 `/usr/bin/python3.12`로 연결되며 실행 결과가 Python 3.12.3 / Unicode 15.0.0이다. `/usr/bin`, `/usr/local/bin`, `/opt` 검색에서도 다른 Python 인터프리터를 찾지 못했다. 이 환경에 없는 Unicode 버전의 동작을 확인했다고 주장하지 않는다. 계약이 지정한 Python 3.12 환경에서 전체 코드 포인트 검증을 완료했다.
- 출력 실패도 실행했다. `/dev/full` 및 끊어진 파이프에서 Python은 120, Rust는 101이다. stdin 닫힘은 Python 1/Rust 0, stdout 닫힘은 1/0, stderr 닫힘 상태에서 사용법 오류는 1/2이다. `python3 verify/check_closed_stdio.py` 및 `verify/check_edges.py`로 재현하며 `reports/closed_stdio_results.json`에 기록했다. 계약 6절이 명시적으로 제외하므로 수정하지 않았다. 확인 완료 항목이며 미확인으로 남기지 않는다.
- 줄바꿈이 포함된 없는 파일 이름의 오류 메시지는 양쪽 모두 실제 LF가 2개다. `reports/newline_filename_results.json`에 실행 결과를 기록했다.
- 수정 후 `cargo fmt --check`, `cargo clippy --all-targets -- -D warnings`, `cargo test`, `cargo build --release`를 모두 `--manifest-path rust_app/Cargo.toml`로 재실행해 통과했다. Rust 단위 테스트 0개, 차등 검증 스크립트로 동작을 확인했다. 고정 비교도 최종 빌드에서 36/36 일치했다. 최종 코드의 `env UV_CACHE_DIR=/tmp/mdtoc-uv-cache PYTHONDONTWRITEBYTECODE=1 uv run python .rustify/fuzz_cli.py --rust rust_app/target/release/mdtoc --examples 2000 --seed 20261101`도 2,000/2,000 일치했다.

## 3. 사람이 결정할 계약·기준 구현의 차이

다음은 추측이나 미실행 항목이 아니라 실행으로 확인한 차이다. 사용자 지시에 따라 이 동작을 바꾸는 수정은 하지 않았다.

1. **긴 수준 정수**: 계약은 수준이 1~6인 정수라고만 정한다. 예를 들어 `--min-level`에 `0` 4,300개와 `1`을 붙인 4,301자리 문자열을 주면 수학적 값은 1이지만 Python은 기본 정수 자릿수 제한 때문에 오류 2로 거부한다. Rust는 값 1로 받아들인다. 밑줄은 숫자 자리 수에서 제외되며 Unicode 십진 숫자에서도 같은 차이가 재현되었다. 계약에 Python 자릿수 제한을 추가할지 사람이 결정해야 한다.
2. **도움말과 잘못된 인자의 우선순위**: Python은 `-hh`, `-hx`를 도움말 0으로 처리하며, `--js --help`처럼 알 수 없는 옵션 뒤의 도움말도 0으로 끝낸다. Rust는 알 수 없는 옵션 오류 2로 처리한다. 계약은 알 수 없는 옵션/약어는 오류 2, `-h`/`--help`는 0이라고 정하지만 이 결합의 우선순위나 `-h` 뒤 문자열 허용을 정하지 않는다. 추가 인자 오류보다 도움말이 우선하는 결합도 같은 분류다. 명령행 전수 검사에서 남은 차이 1,828개는 모두 Python 0/Rust 2인 이 부류이며 개별 인자는 JSON 증거에 있다.
3. **파일 이름에 LF가 있는 오류 메시지**: 계약 5절은 읽기 오류를 한 줄로 정하지만 Python은 파일 이름의 LF를 그대로 출력해 두 줄이 된다. Rust도 같은 이름 표시 동작을 유지한다. 파일 이름을 이스케이프할지, 한 줄 요구의 예외로 둘지 사람이 정해야 한다.

계약 범위 내에서 위에 나열한 충돌·우선순위 결정 외의 남은 관측 불일치는 없다. 임의 길이 문자/인자 조합 전체나 이 환경에 없는 Python 버전의 전수 검증을 완료했다는 의미는 아니다.
