# wordstats 수정 보고서

수정한 파일은 `src/lib.rs` 하나뿐이다. `src/main.rs`, `tests/`, `python_src/`, `Cargo.toml` 은 고치지 않았다.

## 1. 고친 문제 목록

| # | 위치 | 오류 코드 / 검사 | 원인 | 고친 방법 |
|---|------|------------------|------|-----------|
| 1 | `src/lib.rs` `normalize` | E0515 | 함수 안에서 만든 `String`(`lower`)을 빌린 `&str` 을 반환함 | 반환 타입을 `String` 으로 바꾸고 trim 결과를 `to_string()` 으로 반환. Python 도 새 문자열을 반환하므로 동작은 같다 |
| 2 | `src/lib.rs` `tokenize` | (#1 의 후속) | `normalize` 가 `String` 을 반환하게 되어 `.map(str::to_string)` 이 불필요해짐 | 해당 단계 제거 |
| 3 | `src/lib.rs` `count` / `summary` | E0382 (borrow of moved value `words`), E0308 (`tests/spec.rs` 가 `count(&tokenize(..))` 로 호출) | `count` 가 `Vec<String>` 을 소유권째 받아 `summary` 에서 이후 `words` 를 쓸 수 없었고, 테스트의 호출 형태와도 맞지 않았음 | 시그니처를 `count(words: &[String])` 로 바꾸고 키는 `clone()` |
| 4 | `src/lib.rs` `drop_rare` | E0502 | `counts.iter()` 로 빌린 채 반복 중에 `counts.remove()` 호출 | `counts.retain(\|_, n\| *n >= min)` 로 교체 (Python 과 같이 `n < min` 인 항목 삭제) |
| 5 | `src/lib.rs` `merge` | E0499 + 동작 불일치 | `get_mut(source)` 와 `entry(target)` 로 가변 대여가 두 번 겹침. 또 source 를 지우지 않고 0 으로 남겨 두었고, `source == target` 이면 값이 두 배가 될 수 있었음 | Python 처럼 `source == target` 이면 바로 반환, 아니면 `counts.remove(source)` 로 꺼낸 값을 `target` 에 더함 |
| 6 | `src/lib.rs` `longer` | E0106 | 두 `&str` 인자를 받고 `&str` 을 반환하는데 lifetime 을 추론할 수 없음 | `longer<'a>(a: &'a str, b: &'a str) -> &'a str` |
| 7 | `src/lib.rs` `longest` | clippy `len_zero`, `needless_range_loop` (컴파일 오류 해결 후 예상되는 경고) | `words.len() == 0`, 인덱스 기반 `for i in 1..len` | Python 구조대로 `Option<&str>` 을 들고 이터레이터로 순회. 동률이면 먼저 나온 단어를 유지하는 동작은 그대로 |
| 8 | `src/lib.rs` `top_n` | 동작 불일치 (`top_n_breaks_ties_by_word`, `summary_matches_python`) + clippy `needless_return` | 동률일 때 단어를 내림차순(`b.0.cmp(&a.0)`)으로 정렬함. Python 은 `(-count, word)` 로 단어 오름차순 | `a.0.cmp(&b.0)` 로 수정, `return items;` → `items` |
| 9 | `src/lib.rs` `summary` | E0597 | 반복문 안의 임시 `String`(`line`)을 빌린 `&str` 을 반복문 밖 `Vec<&str>` 에 넣음 | `Vec<String>` 에 `format!` 결과를 소유권째 넣고 `join` |
| 10 | `src/lib.rs` `longer` | `cargo fmt --check` | lifetime 을 추가해 시그니처가 길어지면서 한 줄 `if/else` 가 rustfmt 기준을 넘김 | `cargo fmt` 적용 |

## 2. 세 가지 검사의 마지막 실행 결과 (직접 실행)

- `cargo fmt --check`: 통과 (출력 없음, `cargo fmt` 적용 후 재실행)
- `cargo clippy --all-targets -- -D warnings`: 통과 (`Finished`, 경고 없음)
- `cargo test`: 통과 (`tests/spec.rs` 11 passed, 0 failed; 단위/문서 테스트는 0개)

`clippy` 와 `test` 는 `cargo fmt` 를 적용한 뒤 다시 실행한 결과다.

## 3. 고치지 못한 것과 그 이유

테스트와 Python 기준 구현 사이의 불일치는 발견하지 못했다.

다만 `src/main.rs` 의 명령줄 처리는 Python `argparse` 와 다음 경우에 다르게 동작한다. 테스트 대상이 아니고 공개 라이브러리 함수도 아니어서, 기준 동작을 임의로 해석해 바꾸지 않고 기록만 남긴다.

- 음수 값(`--top -1` 등): Python 은 받아들여 슬라이스 `[:-1]` 의미로 쓰지만, Rust 는 `usize` 파싱 실패로 종료 코드 2
- `--top=3` 형식과 `--to 3` 같은 접두어 축약: Python 은 받아들이지만 Rust 는 오류
- `-h/--help`: Python 은 도움말을 출력하고 종료 코드 0, Rust 는 오류(종료 코드 2)
