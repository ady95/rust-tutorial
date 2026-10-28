# wordstats 수정 보고서

## 1. 고친 문제 목록

모두 `src/lib.rs` 에서 고쳤다. `src/main.rs`, `tests/spec.rs`, `python_src/wordstats.py`, `Cargo.toml` 은 바꾸지 않았다.

| 위치 | 검사 / 분류 | 원인 | 고친 방법 |
|---|---|---|---|
| `normalize` | 컴파일 오류 (수명) | 지역 변수 `lower` 를 빌려 `&str` 을 반환해 댕글링 참조가 된다 | 반환형을 `String` 으로 바꾸고 `to_string()` 으로 소유권을 넘긴다 |
| `tokenize` | 컴파일 오류 (`normalize` 반환형 변경에 따른 연쇄) | `normalize` 가 `&str` 을 반환하던 것을 전제로 `str::to_string` 을 썼다 | `normalize` 를 `String` 으로 맞춰 `map` / `filter` / `collect` 로 정리 |
| `count` | 컴파일 오류 (소유권) | `Vec<String>` 을 받아 `summary` 에서 이후 `words` 를 다시 써야 해 이동 후 사용 오류가 난다. 테스트도 `count(&tokenize(..))` 로 호출하므로 참조를 받아야 한다 | 시그니처를 `&[String]` 으로 바꾸고 `w.clone()` 으로 키를 만든다 |
| `drop_rare` | 컴파일 오류 (빌림) | `iter()` 를 돌면서 같은 맵을 `remove` 해 가변/불변 빌림이 충돌한다 | `retain(|_, n| *n >= min)` 으로 바꿔 Python 의 `n < minimum` 제거 규칙과 같게 한다 |
| `merge` | 동작 불일치 (테스트 `merge_moves_count_and_removes_source` 실패 원인) | source 를 지우지 않고 값만 0 으로 만들었다. Python 은 `pop` 으로 항목을 지운다 | `counts.remove(source)` 로 항목을 지우고 그 값을 target 에 더한다. `source == target` 이면 바로 반환한다 |
| `longer` | 컴파일 오류 (수명 생략 규칙) | 입력이 두 개인 `&str` 에서 반환 수명을 정할 수 없다 | `<'a>` 를 명시해 `&'a str` 을 입출력으로 쓴다. 글자 수 비교는 Python `len` 과 같게 `chars().count()` 를 유지했다 |
| `longest` | clippy `len_zero` 계열 정리 및 `longer` 변경에 따른 정리 | `len() == 0` 검사와 인덱스 루프를 썼다 | `iter().map(String::as_str).reduce(longer)` 로 바꿨다. 빈 입력이면 `None` 이고, 먼저 나온 단어가 우선한다 (Python 과 같다) |
| `top_n` | 동작 불일치 (테스트 `top_n_breaks_ties_by_word` 실패 원인) | 횟수가 같을 때 단어를 내림차순으로 정렬했다. Python 은 오름차순이다 | `a.0.cmp(&b.0)` 로 바꿨다. 마지막의 `return items;` 는 clippy `needless_return` 을 피하려고 제거했다 |
| `summary` | 컴파일 오류 (소유권, 수명) | `count(words)` 로 `words` 를 옮긴 뒤 다시 사용했고, `lines` 가 루프 안의 임시 `String` 을 참조했다 | `count(&words)` 로 빌려 쓰고, `lines` 를 `Vec<String>` 으로 만들어 `format!` 결과를 담는다. `longest` 는 `drop_rare` 전이 아니라 전체 단어 기준이다 (Python 과 같다) |

## 2. 세 가지 검사의 마지막 실행 결과

이 세션에서는 셸 명령(Bash)을 쓸 수 없어서 `cargo fmt --check`, `cargo clippy --all-targets -- -D warnings`, `cargo test` 를 직접 실행하지 못했다.
`CLAUDE.md` 에 따라 `.rs` 편집 뒤의 훅(`cargo fmt`, `cargo check --all-targets`)과 작업 종료 시의 훅(`cargo fmt --check`, `cargo clippy`, `cargo test`)이 결과를 전달하도록 되어 있다. 이 보고서를 쓰는 시점에는 그 결과가 도착하지 않았다.

- `cargo fmt --check`: **직접 실행하지 않음 (미확인)**
- `cargo clippy --all-targets -- -D warnings`: **직접 실행하지 않음 (미확인)**
- `cargo test`: **직접 실행하지 않음 (미확인)**

따라서 세 가지 검사가 통과했다고 말할 근거는 없다. 훅 결과를 확인해 실패하면 고친 뒤 다시 실행해야 한다.

코드 검토로 확인한 내용은 다음과 같다. 이는 컴파일러 확인이 아니다.
- `tests/spec.rs` 의 각 테스트 기대값을 `src/lib.rs` 의 새 구현과 대조했다 (`tokenize` 14개, `drop_rare` 결과, `merge` 제거 동작, `top_n` 타이 정렬, `summary` 문자열, 한글 소문자 처리 `élan`).
- `src/main.rs` 는 이미 컴파일 가능해 보여 바꾸지 않았다. 잘못된 숫자 인수는 종료 코드 2 를 낸다.

## 3. 고치지 못한 것과 그 이유

- 고치지 못한 항목은 없다. 다만 위 2번의 검사 결과는 직접 확인하지 못했다.
- 테스트와 Python 기준 구현의 불일치는 찾지 못했다. `tests/spec.rs` 의 기대값과 `python_src/wordstats.py` 의 동작은 서로 맞는다고 판단했다.
- 공백 분리는 Rust `split_whitespace` 와 Python `str.split()` 이 완전히 같지 않을 수 있다(유니코드 공백 범위의 미세한 차이). 테스트 범위에서는 문제가 없어 바꾸지 않았다.
