# port_notes

상태: **미완료**. 예산이 소진되어 마지막 검증(verify/all_codepoints.py)이 실패한 채로 끝났습니다.

## 1. 특별히 처리한 Python 동작
- `str.splitlines()` 경계 글자 전체, `str.strip()` 공백 집합(`\x1c`~`\x1f` 포함), Python `\w`, `int()` 문자열 해석
- Python `\w` 와 십진 숫자 표는 verify/gen_tables.py 가 Python 에서 만들어 rust_app/src/tables.rs 에 넣었습니다
- `str.lower()`: Rust 표준 라이브러리의 유니코드 버전이 Python 과 달라(예: U+0897 이 Σ 의 끝 시그마 판정에 영향) 직접 구현했습니다. 변환 표와 끝 시그마용 Cased·Case_Ignorable 표도 Python 에서 생성했습니다
- argparse 동작(`-h` 우선, 약어 불가, `--opt=value`, 위치 인자 둘이면 오류 등)을 흉내 냈습니다. verify/probe_args.py 로 Python 동작을 먼저 확인했습니다

## 2. 직접 실행해 확인한 것
- 표준 `lower()` 를 쓰던 시점에서: cargo clippy -D warnings, cargo test, cargo build --release, compare 36/36, fuzz 2000건(seed 777) 통과
- verify/all_codepoints.py 의 인자 해석 28건은 Python 과 일치
- 자체 `lower()` 로 바꾼 뒤에는 cargo build --release 만 통과했습니다. 그 뒤 clippy, cargo test, cargo fmt --check, compare, fuzz 는 **다시 실행하지 못했습니다**

## 3. 확신하지 못하는 부분
- **verify/all_codepoints.py 의 코드 포인트 비교가 자체 `lower()` 도입 후에도 실패합니다.** 원인은 확인하지 못했습니다. 이전 실패는 U+0897 등 유니코드 16 에서 추가된 글자 주변의 끝 시그마 차이였습니다. 새 표의 Case_Ignorable 판정 프로브(`"aΣ"+c`)나 Cased 프로브가 틀렸을 수 있습니다. verify/diff_codepoints.py 로 어느 글자가 다른지 확인하면 됩니다
- 자체 `lower()` 이후 compare/fuzz 결과는 미확인입니다. 자체 구현이 회귀를 만들었을 가능성이 있습니다
- 유니코드 표는 실행 환경의 Python 버전에 맞춰 생성했습니다. 다른 버전의 Python 이 기준이면 gen_tables.py 를 다시 실행해야 합니다
