logstat(python_src/logstat.py)은 Python 프로그램으로 그대로 두고, 시간이 많이 드는 부분만 Rust 확장 모듈로 옮겨 주세요(부분 이식).

배경: 기준 구현은 100만 레코드 CSV 에서 약 9.6초가 걸리고, 그중 약 75%가 레코드마다 도는 해석·검증(read_csv/read_jsonl), 약 24%가 집계(summarize)입니다. 출력 문자열 만들기는 거의 0입니다.

## 만들 것

1. `rust_ext/`: maturin + PyO3 0.30 확장 모듈 크레이트. Python 모듈 이름은 `logstat_core`
2. 경계(Python 과 Rust 가 주고받는 것)가 다른 두 가지 진입점
   - `ext/logstat_v1.py`: Rust 는 해석·검증만 한다. `logstat_core` 가 기준 구현의 read_csv/read_jsonl 과 같은 결과(레코드 번호, 레코드 또는 오류 이유, 파일 전체 오류)를 Python 객체로 돌려주고, 집계(summarize)와 출력은 기준 구현의 함수를 그대로 쓴다
   - `ext/logstat_v2.py`: Rust 가 해석·검증·집계까지 한다. `logstat_core` 는 기준 구현의 summarize 가 돌려주는 것과 같은 구조의 dict(실수는 Python float) 또는 오류를 돌려주고, 출력 문자열 만들기(format_text, json.dumps)만 기준 구현의 코드로 한다
   - 두 진입점 모두 기준 구현의 main()(인자 처리, 파일 읽기)을 그대로 쓰고 run() 만 바꾼다(예: 기준 구현 모듈을 import 한 뒤 `module.run = 새 run` 으로 바꾸고 `module.main()` 호출)
   - 실행 파일 `ext/logstat_v1`, `ext/logstat_v2`(셸 스크립트)는 이미 있다. 각각 `.venv/bin/python ext/logstat_v1.py` 와 v2 를 실행한다
3. `port/rust_reference/` 에 09장에서 만든 전체 Rust 이식(바이너리)의 소스가 있다. 해석·검증·집계 코드를 복사해 재사용해도 된다(이 폴더는 읽기만 한다)

## 규칙과 명령

- 확장 빌드·설치: `.venv/bin/maturin develop --release -m rust_ext/Cargo.toml` (작업 폴더의 .venv 에 설치된다. maturin 은 이미 설치되어 있다)
- crates.io 접속이 허용되어 있어 PyO3 등 크레이트를 받을 수 있다
- 출력은 기준 구현과 바이트 단위로 같아야 한다(contracts/behavior_spec.md)

## 완료 조건 (파이프라인이 직접 다시 실행해 판정)

- `cargo fmt --check`, `cargo clippy -- -D warnings` (rust_ext)
- maturin develop --release 성공
- `uv run python automation/compare.py --rust ext/logstat_v1`, 같은 명령으로 `ext/logstat_v2`
- `uv run python automation/fuzz.py --rust ext/logstat_v1 --examples 1000`, v2 도 같게

끝나면 reports/port_notes.md 에 (1) 두 경계에서 Python 과 Rust 가 주고받는 자료와 그 비용에 대한 판단 (2) 직접 실행해 확인한 것 (3) 확신하지 못하는 부분을 적어 주세요.
