# logstat 부분 이식 보고서

## 현재 상태: 일부만 확인됨

| 단계 | 상태 |
|---|---|
| `cargo fmt --check` (rust_ext) | 내가 직접 실행해 통과 확인 |
| `cargo clippy -- -D warnings` | 직접 다시 돌리지 못함. 파이프라인 출력의 유일한 오류(`manual_div_ceil`, summary.rs)를 `div_ceil(100)` 으로 고쳤을 뿐 |
| maturin develop, compare, fuzz | **직접 실행하지 못함** (아래 환경 문제) |

## 실패 원인과 수정

1. **fmt**: 테스트 코드의 줄 모양이 rustfmt 와 달랐다. `cargo fmt` 로 정리했다.
2. **clippy**: `(p * n + 99) / 100` 을 `div_ceil` 로 바꿨다(같은 값, 정수 연산).
3. **compare/fuzz (v1, v2 모두)**: `ext/logstat_v1.py`, `ext/logstat_v2.py` 파일이 없어서 실행 자체가 실패했다(직전 보고에서 이미 "만들지 않았다"고 적은 부분). 두 파일을 만들었다. 둘 다 `python_src/logstat.py` 를 import 하고 `module.run` 을 교체한 뒤 `module.main()` 을 호출한다. 이 오류는 출력 차이가 아니라 파일 부재라서, "같은 원인으로 틀릴 입력"은 없다. 그러나 출력 내용이 맞는지는 아직 한 번도 비교하지 못했다.

(참고: 지시문의 `rust_app/` 은 이 작업에 존재하지 않는다. 수정한 곳은 `rust_ext/` 와 `ext/` 다.)

## 직접 실행하지 못한 이유

내 셸의 `VIRTUAL_ENV` 가 존재하지 않는 `/home/dev/work/rust-tutorial/ch08/porter/.venv` 를 가리켜 `cargo clippy`, `maturin develop` 이 pyo3 빌드 스크립트에서 실패한다(두 번 확인). 환경 변수를 바꿔 실행하는 명령은 훅이 거부한다. 파이프라인 쪽 실행에서는 maturin 이 통과했고 clippy 도 컴파일을 지나 lint 까지 갔으므로, `lib.rs` 의 PyO3 0.30 사용은 타입 검사를 통과한 것으로 보인다. 이것은 파이프라인 출력에서 추정한 것이지 내가 확인한 것이 아니다.

## (1) 두 경계의 자료와 비용 (측정하지 않은 판단)

- **v1**: Python→Rust 는 파일 텍스트(str) 한 번(UTF-8 버퍼를 빌려 쓰므로 복사 없음). Rust→Python 은 레코드마다 `datetime`(UTC) 과 frozen dataclass `Record`(생성자 호출)를 만든다. 100만 건이면 객체 약 200만 개와 파이썬 생성자 호출 100만 번이 든다. 집계는 Python 이 그대로 하므로 약 24% 구간은 줄지 않는다. 이득은 해석·검증 구간에 한정된다.
- **v2**: Python→Rust 는 같은 텍스트 한 번. Rust→Python 은 요약 dict 하나(top N 경로, 메서드 몇 개)라 레코드 수와 무관하다. 비용은 Rust 안에서 레코드를 `Vec<Record>` 로 들고 있는 메모리뿐이다. 더 빠를 것으로 예상하지만 시간은 재지 않았다.

## (2) 직접 실행해 확인한 것

- `cargo fmt --check` 통과.
- 그 외 없음.

## (3) 확신하지 못하는 부분

- 두 진입점의 출력이 기준 구현과 바이트 단위로 같은지 전혀 확인하지 못했다.
- `cargo test` 가 pyo3 를 libpython 에 링크하지 못해 실패할 수 있다(`extension-module` 은 maturin 빌드에서만 켜도록 했으나 확인 못 함). `clippy --all-targets` 도 같다.
- 짝 없는 서로게이트가 든 경로: Rust 에서 `surrogatepass` 로 디코드해 Python str 로 만든다. v1·v2 모두 해당하며 출력 단계에서 기준 구현과 같은 UnicodeEncodeError 동작이 나오는지 확인하지 못했다.
- `--top` 이 u64 를 넘는 값이면 `u64::MAX` 로 둔다(결과는 "전부"로 같을 것으로 추정).
- 성능(약 9.6초 대비)은 측정하지 않았다.
