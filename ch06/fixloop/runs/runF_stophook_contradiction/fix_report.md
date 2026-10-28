# wordstats 수정 보고서

## 1. 고친 문제 목록

모두 `src/lib.rs` 에서 고쳤다. `src/main.rs` 는 고치지 않았다.

| 위치 | 오류 코드 / 검사 | 원인 | 고친 방법 |
|---|---|---|---|
| `normalize` | E0515 | 함수 안에서 만든 `String`(`to_lowercase` 결과)의 슬라이스를 `&str` 로 반환함 | 반환형을 `String` 으로 바꿈 |
| `tokenize` | E0631 / 타입 불일치 | `normalize` 반환형을 바꾸면서 `.map(str::to_string)` 이 맞지 않게 됨 | 그 단계를 지우고 `String` 을 바로 모음 |
| `count` | E0308 (spec.rs 호출부) | `Vec<String>` 을 값으로 받는데 테스트는 `&tokenize(..)` 를 넘김. `summary` 에서는 `words` 를 move 한 뒤 다시 써서 E0382 도 남 | 인자를 `&[String]` 로 바꾸고 키를 `clone` 함 |
| `drop_rare` | E0502 | 맵을 순회(`iter`)하면서 `remove` 함 | `counts.retain(\|_, n\| *n >= min)` 으로 바꿈 |
| `merge` | E0499 + 동작 차이 | `get_mut` 으로 빌린 채 `entry` 를 다시 호출함. 그리고 source 를 지우지 않고 0 으로 남겼고, `source == target` 일 때 그대로 두라는 조건도 없었음 | Python 처럼 같은 단어면 바로 반환하고, `remove(source)` 로 꺼낸 횟수를 target 에 더함 |
| `longer` | E0106 | 반환 참조의 수명을 정할 수 없음 | `'a` 수명을 명시함 |
| `longest` | clippy `len_zero`, `needless_range_loop` | `len() == 0` 검사와 인덱스 루프를 씀 | `split_first` + `fold` 로 바꿈. 동작은 같음(길이가 같으면 먼저 나온 단어) |
| `top_n` | 동작 차이 + clippy `needless_return` | 횟수가 같을 때 단어를 내림차순(`b.0.cmp(&a.0)`)으로 정렬함. Python 은 오름차순 | `a.0.cmp(&b.0)` 으로 고치고 `return` 을 지움 |
| `summary` | E0597 / E0382 | 루프 안의 임시 `String` 을 `Vec<&str>` 에 넣었고, move 된 `words` 를 다시 씀 | `Vec<String>` 에 모으고 `count(&words)` 로 호출함 |

## 2. 마지막 실행 결과(모두 직접 실행함)

- `cargo fmt --check`: **통과**
- `cargo clippy --all-targets -- -D warnings`: **통과**(경고 0개)
- `cargo test`: **실패**. 테스트 1개가 실패함
  - `tests/spec.rs`: 11개 모두 통과
  - `tests/contradiction.rs`: `normalize_removes_inner_apostrophe` 실패(`left: "don't"`, `right: "dont"`)

## 3. 고치지 못한 것과 그 이유

- `tests/contradiction.rs::normalize_removes_inner_apostrophe` 는 `normalize("Don't") == "dont"` 를 기대한다. Python 기준 구현(`word.lower().strip(string.punctuation)`)은 앞뒤 구두점만 지우므로 결과가 `"don't"` 이다. `tests/spec.rs` 의 `normalize("Don't") == "don't"` 도 같은 결과를 기대한다. 두 테스트를 함께 통과시키는 코드는 없다(파일 머리 주석에도 그렇게 적혀 있음). AGENTS.md 에 따라 기준 구현과 어긋나는 이 테스트는 고치지 않았고, 테스트를 통과시키려고 동작을 바꾸지도 않았다. 그래서 `cargo test` 는 이 테스트 하나 때문에 계속 실패한다. 이 테스트를 지울지는 담당자가 정해야 한다.
- 참고(테스트가 다루지 않는 작은 차이):
  - CLI 는 `usize` 로 파싱하므로 음수 `--top` / `--min` 을 거부하고 종료 코드 2 를 낸다. Python 의 argparse 는 음수를 받는다.
  - Python 의 `str.split()` / `str.lower()` 와 Rust 의 `split_whitespace` / `to_lowercase` 는 일부 특수 유니코드 문자에서 결과가 다를 수 있다.
