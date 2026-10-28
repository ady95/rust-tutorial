# stats 이식 보고서

`python_src/stats.py` → `rust_app/` (실행 파일 `stats`, 외부 크레이트 없음)

- `src/main.rs` — 인자 처리, 파일 읽기, 줄 파싱, 출력, 오류 메시지
- `src/pyfloat.rs` — Python의 `repr(float)`, `round`, `:.4f`, `float()` 파싱, `str.splitlines`/`str.strip` 동작
- `src/stats.rs` — 내장 `sum`/`min`/`max`, `statistics.mean`/`statistics.stdev`
- `src/bigint.rs` — 위 계산에 쓰는 최소한의 부호 없는 큰 정수

## 1. Python과 Rust의 동작 차이 때문에 특별히 처리한 것

| 항목 | Python 동작 | Rust 쪽 처리 |
|---|---|---|
| `repr(float)` | 왕복이 보장되는 가장 짧은 자릿수. 10진 소수점 위치가 -4 이하이거나 16을 넘으면 `1e+16`, `1e-05`처럼 지수 표기(지수는 최소 2자리). 정수 값은 `3.0` | Rust의 `{}`는 `3`을 내고 지수 표기를 쓰지 않음. `{:e}`로 가장 짧은 자릿수를 얻은 다음 Python 규칙대로 다시 조립함 (`pyfloat::repr`) |
| `sum()` | CPython 3.12는 float 합에 Neumaier 보정 합을 쓰고, 시작값이 int `0`이어서 `-0.0`이 `0.0`이 됨 | 같은 알고리즘을 그대로 옮김. 마지막에 `c`가 0이 아니고 유한할 때만 더함 (`stats::py_sum`) |
| `statistics.mean` | 각 값을 정확한 분수(Fraction)로 더한 뒤 n으로 나누고, 결과를 한 번만 올바르게 반올림함 | 유한한 float는 모두 2^-1074의 정수배라서 2^1074를 곱한 큰 정수로 정확히 합산함. 나눗셈은 sticky 비트를 남기고, 비정규수까지 고려해 최근접·짝수 반올림을 직접 구현함 |
| `statistics.stdev` | 3.12에서는 `(nΣx² − (Σx)²)/(n(n−1))`를 정확한 분수로 계산하고 `_float_sqrt_of_frac`로 올바르게 반올림한 제곱근을 구함 | 같은 식을 큰 정수로 계산함. 몫이 약 2^122~2^125가 되도록 짝수 비트만큼 시프트하고, u128 정수 제곱근과 sticky 비트로 올바르게 반올림함 |
| `round(x, 2)` | 정확한 10진 값을 기준으로 반올림하고(동점이면 짝수), 결과를 다시 float로 읽음. 예: `round(2.675, 2) == 2.67`, `round(0.125, 2) == 0.12` | `format!("{:.2}")`(정확한 값 기준, 동점이면 짝수)으로 만든 문자열을 `parse`함. 단위 테스트로 확인함 |
| `:.4f` | 동점이면 짝수로 감. NaN은 `nan` | `{:.4}`를 쓰되 Rust가 `NaN`으로 출력하므로 따로 처리함 |
| `min`/`max` | 첫 원소부터 시작해서 `x < cur` / `x > cur`일 때만 교체함. `-0.0`과 `0.0`이 같으면 먼저 나온 값을 유지함 | 같은 방식의 fold로 구현함 |
| `float()` 파싱 | 숫자 사이에 오는 `_`를 허용함(`1_000`). `inf`/`infinity`/`nan`은 대소문자를 가리지 않고 부호를 붙일 수 있음 | Rust `parse`는 `_`를 받지 않음. Python 규칙으로 밑줄을 검사·제거하고 문법을 확인한 뒤 `parse`함 |
| `str.strip()` | `\x1c`–`\x1f`도 공백으로 봄 | Rust `trim()`은 이 문자들을 공백으로 보지 않음. `is_py_space`를 따로 만듦 |
| `str.splitlines()` | `\r`, `\r\n`, `\x0b`, `\x0c`, `\x1c`–`\x1e`, `\x85`, U+2028, U+2029에서도 줄을 나눔 | Rust `lines()`는 `\n`/`\r\n`에서만 나눔. 줄 번호가 같도록 직접 구현함 |
| UTF-8 디코딩 오류 | `UnicodeDecodeError`는 `ValueError`이므로 `stats: error: 'utf-8' codec can't decode byte 0x.. in position N: <이유>` 형식으로 출력되고 종료 코드는 1 | `Utf8Error`의 `valid_up_to`/`error_len`으로 위치와 이유(`invalid start byte` / `invalid continuation byte` / `unexpected end of data`)를 맞추고, 여러 바이트일 때는 `bytes in position A-B` 형식을 씀 |
| 줄 끝 | `reconfigure(newline="\n")` | 항상 `\n`만 씀 |
| 종료 코드 | 인자 개수가 틀리면 2, 그 밖의 오류는 1 | 같음 |

## 2. 완료 조건 마지막 실행 결과 (직접 실행한 것)

- `cargo fmt --check` — 통과 (`FMT_OK` 출력)
- `cargo clippy -- -D warnings` — 통과. 첫 실행에서 `splitlines`의 중첩 `if`에 대한 지적 1건이 나와 `next_if`로 고친 뒤 다시 실행해 경고 없이 끝남
- `cargo build --release` — 통과
- `python3 compare.py` — 통과, `8/8 cases match`
- 참고로 `cargo test`도 통과함(단위 테스트 8개: repr, round, 파싱, splitlines, mean/stdev 반올림, sum 보정)

## 3. 같다고 확신하지 못하는 부분

이 환경에서는 `compare.py` 말고는 임의의 Python 실행과 표준 라이브러리 소스 열람이 승인되지 않았습니다. 그래서 아래 경계 입력은 Python과 **직접 대조하지 못했고**, CPython 3.12에 대한 지식으로 구현했습니다. 대조용 스크립트는 `scratch/probe.py`에 남겨 두었습니다(`python3 scratch/probe.py rust_app/target/release/stats`).

- **inf/nan이 섞인 입력**: 3.12의 `statistics.stdev`는 `_ss`가 float를 돌려주는데, 그 float에서 `.numerator`를 찾다가 `AttributeError` traceback으로 끝날 것으로 봤습니다. Rust 쪽은 종료 코드 1과 마지막 줄 `AttributeError: 'float' object has no attribute 'numerator'`만 냅니다. traceback 본문은 재현하지 않았으므로 **이 경우 stderr는 다릅니다**. 추정 자체가 틀렸을 수도 있습니다.
- **Unicode 숫자**: Python `float()`는 비ASCII 10진 숫자(예: 전각 `２`)도 받습니다. Rust 쪽은 유니코드 숫자 표 없이 ASCII만 받으므로 이런 줄은 "not a number" 오류가 됩니다. **차이가 있다는 것을 알고 있습니다.**
- **`sum()` 마무리 조건**: `if (c && Py_IS_FINITE(c))`가 3.12.3의 실제 코드와 같다고 기억에 의존했습니다. 합이 넘쳐서 inf가 되는 경우에만 영향을 줍니다.
- **UTF-8 오류 메시지**: 첫 바이트가 C2–F4이면 "invalid continuation byte", 아니면 "invalid start byte"로 구분했습니다. 범위의 끝은 Rust의 maximal-subpart 길이와 같다고 가정했습니다.
- **파일 이름**: UTF-8이 아닌 경로 인자는 Python의 surrogateescape와 달리 손실 변환(`to_string_lossy`)으로 출력합니다.
- **stdev가 비정규수 범위인 경우**: 구현상으로는 올바르게 반올림하지만, Python `_float_sqrt_of_frac`의 비정규수 처리와 같은지는 대조하지 못했습니다.
- n이 2^32 이상이면 `n(n−1)`이 u64를 넘으므로 패닉합니다(현실적인 입력에서는 해당 없음).
