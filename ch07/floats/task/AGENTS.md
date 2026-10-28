# stats 이식 지침

## 목표

`python_src/stats.py` 를 Rust 로 다시 구현한다. 결과물은 `rust_app/` 의 Cargo 프로젝트(실행 파일 이름 `stats`).

같은 입력 파일에 대해 stdout·stderr·종료 코드가 Python 기준 구현과 **바이트 단위로 같아야** 한다.
`python3 compare.py` 가 `cases/` 의 입력으로 두 구현을 비교한다.

## 규칙

- `python_src/`, `cases/`, `compare.py` 는 고치지 않는다
- 표준 라이브러리만 쓴다(외부 크레이트 금지)
- 완료 조건: `cargo fmt --check`, `cargo clippy -- -D warnings`, `cargo build --release`, `python3 compare.py` 모두 통과

## 보고서

끝나면 `reports/port_report.md` 에 적는다.

1. Python 과 Rust 의 동작 차이 때문에 특별히 처리한 것
2. 완료 조건의 마지막 실행 결과(직접 실행한 것만 통과로 적는다)
3. 같다고 확신하지 못하는 부분
