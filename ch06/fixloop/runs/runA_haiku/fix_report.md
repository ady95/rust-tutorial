# wordstats 수정 보고서

대상: `src/lib.rs` (`src/main.rs`, `Cargo.toml`, `tests/spec.rs`, `python_src/` 는 수정하지 않았다)

## 1. 고친 문제 목록

| 위치 | 오류 코드 / 검사 | 원인 | 고친 방법 |
|---|---|---|---|
| `src/lib.rs` `normalize` (기존 :5-8) | E0515 (`cannot return value referencing local variable`) | 소문자 변환한 `String` 지역 변수의 `&str` 조각을 반환 | 반환 타입을 `String` 으로 바꾸고 `.to_string()` 으로 소유권 있는 값을 반환. `tokenize` 에서 `.map(str::to_string)` 제거 |
| `src/lib.rs` `count` (기존 :18) | E0382 (`borrow of moved value: words`) | `count` 가 `Vec<String>` 을 소유권째로 받아 `summary` 에서 `words` 를 다시 쓸 수 없음 | 시그니처를 `&[String]` 으로 바꾸고 내부에서 `w.clone()` 으로 키를 만듦. `tests/spec.rs` 가 `count(&tokenize(TEXT))` 로 호출하므로 이 시그니처가 명세와도 맞음 |
| `src/lib.rs` `drop_rare` (기존 :26-32) | E0502 (`cannot borrow *counts as mutable because it is also borrowed as immutable`) | 순회 중 `counts.remove` 호출 | `counts.retain(\|_, n\| *n >= min)` 로 교체. 기준은 Python 과 같이 `n < minimum` 인 항목만 제거 |
| `src/lib.rs` `merge` (기존 :35-41) | E0499 (`cannot borrow *counts as mutable more than once`) | `get_mut` 으로 얻은 `src` 를 살린 채 `entry` 를 호출 | 먼저 `counts.remove(source)` 로 꺼내고, 값이 있으면 `target` 에 더함. 같은 단어면 즉시 반환. 이전 코드의 `*src = 0` 은 키를 지우지 않아 `tests/spec.rs` 의 `counts.get("cat") == None` 을 어겼으므로 함께 바로잡음 (Python `counts.pop(source)` 와 일치) |
| `src/lib.rs` `longer` (기존 :43) | E0106 (`missing lifetime specifier`) | 입력 두 개와 반환값의 수명 관계가 명시되지 않음 | `fn longer<'a>(a: &'a str, b: &'a str) -> &'a str` 로 수명 명시. 본문은 `if/else` 블록 형태로 정리 |
| `src/lib.rs` `longest` (기존 :47-56) | 컴파일 오류는 없음. clippy 기준 선제 정리 (`len_zero`, `needless_range_loop` 계열) | `len() == 0` 사용, 인덱스 루프 (원래 코드는 클리피 단계까지 도달하지 못해 실제 클리피 출력은 확인하지 못함) | `words.iter().map(String::as_str).reduce(longer)` 로 교체. 앞의 단어가 이기는 동작(동률이면 먼저 나온 것)은 그대로 유지 |
| `src/lib.rs` `top_n` (기존 :58-63) | 동작 오류 (테스트 `top_n_breaks_ties_by_word` 기준) + clippy `needless_return` | 동률 정렬을 `b.0.cmp(&a.0)` 로 해서 단어를 내림차순으로 정렬. Python 은 `(-count, word)` 로 단어 오름차순 | `a.0.cmp(&b.0)` 로 바꿔 단어 오름차순으로 맞춤. 마지막 `return items;` 는 `items` 로 바꿈 |
| `src/lib.rs` `summary` (기존 :65-81) | E0597 (`line` does not live long enough) | `lines: Vec<&str>` 에 지역 `String` 의 `as_str()` 을 넣음 | `lines` 를 `Vec<String>` 으로 바꾸고 `format!` 결과를 직접 push. `count(&words)` 로 호출 변경 |

## 2. 세 가지 검사의 마지막 실행 결과

위 수정 후 같은 셸 호출에서 `&&` 로 이어 실행했다. 세 명령 모두 성공하고 종료 코드는 0 이다.

- `cargo fmt --check`: 출력 없음, 성공 (통과)
- `cargo clippy --all-targets -- -D warnings`: 경고/오류 없이 `Finished` (통과)
- `cargo test`: 통과
  - `tests/spec.rs` 11 개 테스트 모두 `ok` (11 passed; 0 failed)
  - lib, bin, doc-test 는 테스트 0 개로 `ok`

Python 기준 구현(`python_src/wordstats.py`)은 실행하지 않았다. 기대값은 `tests/spec.rs` 가 가진 Python 출력 값으로만 확인했다.

## 3. 고치지 못한 것과 그 이유

- 없음. 세 검사가 모두 통과했다.
- 참고: `count` 와 `normalize` 의 공개 시그니처가 바뀌었다 (`count(Vec<String>)` → `count(&[String])`, `normalize(&str) -> &str` → `-> String`). 원래 코드는 컴파일되지 않았고 `tests/spec.rs` 가 `count(&tokenize(TEXT))` 로 호출하므로 이 변경은 명세에 맞추기 위해 필요했다. 외부 호출자가 있다면 영향이 있다.
- 참고: `merge` 의 동작 수정(원본 `*src = 0` → 키 제거)과 `top_n` 의 동률 정렬 방향 수정은 컴파일 오류 해결이 아니라 Python 기준 및 명세에 맞추기 위한 동작 변경이다. 두 항목을 포함해 `tests/spec.rs` 와 어긋나던 부분을 모두 바로잡았다.
