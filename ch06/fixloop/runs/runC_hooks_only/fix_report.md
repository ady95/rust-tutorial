# wordstats 수정 보고서

## 1. 고친 문제 목록

모두 `src/lib.rs` 에 있다. `src/main.rs`, `tests/spec.rs`, `python_src/`, `Cargo.toml` 은 고치지 않았다.

| 위치 | 오류 코드 / 검사 | 원인 | 고친 방법 |
|---|---|---|---|
| `normalize` | E0515 | 함수 안에서 만든 `String`(`lower`)을 빌린 `&str` 를 반환 | 반환 타입을 `String` 으로 바꿈 |
| `tokenize` | (`normalize` 변경에 따른 타입 오류) | `.map(str::to_string)` 이 `&str` 를 가정 | `normalize` 가 `String` 을 주므로 해당 단계 제거 |
| `tokenize` | 동작 차이 (Python 기준) | `split_whitespace` 는 Python `str.split()` 이 공백으로 보는 U+001C..U+001F 를 공백으로 보지 않음 | `char::is_whitespace` 에 U+001C..U+001F 를 더한 술어로 나누고, 빈 조각은 기존 필터로 버림 |
| `count` | E0308 (테스트가 `count(&tokenize(..))` 로 호출) / `summary` 의 E0382 | `Vec<String>` 을 값으로 받아 `summary` 에서 `words` 가 이동된 뒤 다시 쓰임 | 인자를 `&[String]` 로 바꾸고 단어를 `clone` 해서 셈 |
| `drop_rare` | E0502 | `counts.iter()` 로 빌린 채 `counts.remove` 호출 | `HashMap::retain(|_, n| *n >= min)` 사용 |
| `merge` | E0499, 동작 차이 | `get_mut` 과 `entry` 로 가변 대여 두 번. 또 source 를 지우지 않고 0으로 남겼고, source == target 이면 Python 과 달리 처리됨 | source == target 이면 바로 반환, 아니면 `remove(source)` 한 값을 target 에 더함 |
| `longer` | E0106 | 반환 참조의 수명을 추론할 수 없음 | 수명 매개변수 `'a` 명시 |
| `longest` | clippy `len_zero`, `needless_range_loop` | `len() == 0` 비교, 인덱스 루프 | `Option` 누적으로 다시 작성(같으면 먼저 나온 것 유지 — 동작 동일) |
| `top_n` | 동작 차이 (`top_n_breaks_ties_by_word`), clippy `needless_return` | 횟수가 같을 때 단어를 내림차순(`b.0.cmp(&a.0)`)으로 정렬. Python 은 오름차순 | `a.0.cmp(&b.0)` 로 바꾸고 `return` 제거 |
| `summary` | E0597, E0382 | 루프 안 임시 `String` 의 참조를 `Vec<&str>` 에 넣음. 이동된 `words` 사용 | `Vec<String>` 으로 줄을 모음, `count(&words)` 로 빌려 줌 |

## 2. 세 가지 검사의 마지막 실행 결과

이 세션에서는 Bash 를 쓸 수 없어 **내가 직접 실행한 검사는 없다.** 검사는 프로젝트 훅(`.claude/hooks/after_edit.py`, `before_stop.py`)이 실행한다.

- `src/lib.rs` 수정 후 편집 훅(`cargo fmt`, `cargo check --all-targets`)은 오류를 보고하지 않았다.
- `cargo fmt --check`, `cargo clippy --all-targets -- -D warnings`, `cargo test`: 종료 훅 결과를 아래에 적는다.

(종료 훅 결과: 작성 시점 기준 미확인)

## 3. 고치지 못한 것과 그 이유

테스트와 Python 기준 구현이 어긋나는 곳은 찾지 못했다(테스트 기대값을 Python 정의대로 손으로 따라가 확인함, Python 을 실제로 실행하지는 못함).

CLI(`src/main.rs`)는 테스트를 통과하는 범위에서 고치지 않았지만, Python `argparse` 와 다음이 다르다.

- `--top -1` 처럼 음수: Python 은 받아들이고(`--top -1` 이면 슬라이스 `[:-1]` 로 마지막 줄 하나를 뺌), Rust 는 `usize` 파싱 실패로 종료 코드 2.
- `--top=3` 형식, `--to 3` 같은 접두어 축약: Python 은 받아들이고, Rust 는 거부.
- 같은 옵션 반복, `-h/--help` 처리와 오류 메시지 형식도 다르다.

이를 맞추려면 음수 `top`/`min` 의미를 라이브러리 API(`usize`)까지 바꿔야 해서 테스트 시그니처와 충돌할 수 있어 손대지 않았다.

그 밖에 Python `str.lower()` 와 Rust `to_lowercase()` 는 유니코드 버전 차이 때문에 드문 문자에서 결과가 다를 수 있다(확인하지 않음).
