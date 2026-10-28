# wordstats 수정 지침

## 목표

`src/` 의 Rust 코드를 고쳐 다음 세 가지를 모두 통과시킨다.

```
cargo fmt --check
cargo clippy --all-targets -- -D warnings
cargo test
```

## 기준

- 동작의 기준은 `python_src/wordstats.py` 와 `tests/spec.rs` 다. 둘 다 고치지 않는다
- `Cargo.toml` 은 고치지 않는다(의존성 추가 금지)
- 컴파일 오류를 없애려고 동작을 바꾸지 않는다. 공개 함수의 동작은 Python 기준 구현과 같아야 한다
- 테스트가 Python 기준 구현과 어긋난다고 판단되면 고치지 말고 보고서에 적는다

## 보고서

끝나면 `reports/fix_report.md` 에 다음을 적는다.

1. 고친 문제 목록: 위치, 오류 코드 또는 검사 이름, 원인, 고친 방법
2. 세 가지 검사의 마지막 실행 결과(직접 실행한 것만 통과로 적는다)
3. 고치지 못한 것과 그 이유
