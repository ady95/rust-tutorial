# fix_report — tokenize 의 Cow 리팩터링

요청: `tokenize` 가 단어마다 `String` 을 새로 만들지 않게 하고(`std::borrow::Cow`),
`tokenize` 를 쓰는 함수도 복사를 줄인다. `tests/spec.rs`, `python_src/wordstats.py`, `Cargo.toml` 은 고치지 않았다.

시작 시점에 세 검사는 이미 모두 통과했다. 그래서 이번 작업은 오류 수정이 아니라 리팩터링이다.

## 1. 바꾼 것 (모두 `src/lib.rs`)

| 위치 | 검사/이유 | 원인 | 바꾼 방법 |
|---|---|---|---|
| `normalize` | 복사 줄이기 | 단어마다 `to_lowercase()` 와 `to_string()` 으로 String 을 두 번 만들었다 | 반환형을 `Cow<'_, str>` 으로 바꿨다. 앞뒤 ASCII 문장부호를 먼저 떼고, 모든 글자가 `c.to_lowercase() == [c]` 이면 입력 조각을 빌려 쓰고(`Borrowed`), 아니면 그때만 `to_lowercase()` 로 새로 만든다(`Owned`) |
| `tokenize` | 복사 줄이기 | `Vec<String>` 을 반환했다 | `Vec<Cow<'_, str>>` 를 반환한다. 테스트의 `words[0] == "the"` 는 `Cow<str>: PartialEq<&str>` 로 그대로 컴파일된다 |
| `count` | `Cow` 입력 받기, 복사 줄이기 | `&[String]` 만 받았고 단어마다 `w.clone()` 했다 | `count<S: AsRef<str>>(&[S])` 로 바꿨다. `get_mut` 로 먼저 찾아서 키 String 은 처음 나온 단어에만 만든다. 반환형 `HashMap<String, usize>` 는 그대로 두었다(테스트의 `sorted`, `merge` 가 이 타입을 쓴다) |
| `longest` / `longest_of` (새 비공개 함수) | `Cow` 입력 받기 | `summary` 가 `Cow` 벡터로 `longest` 를 불러야 한다 | 공개 `longest(&[String])` 시그니처는 그대로 두었다. 이것을 제네릭으로 바꾸면 테스트의 `longest(&[])` 에서 타입을 추론하지 못해 컴파일이 안 된다. 그래서 본체를 비공개 제네릭 `longest_of<S: AsRef<str>>` 로 옮겼고, `longest` 와 `summary` 가 이 함수를 부른다 |
| `top_n` | 복사 줄이기 | 모든 항목을 `(String, usize)` 로 복사한 뒤 정렬하고 잘랐다 | `(&String, &usize)` 참조로 정렬하고 자른 다음 남은 n 개만 복사한다. 반환형은 같다 |
| `summary` | 위 변경에 맞춤 | — | `tokenize` → `count(&words)` → `longest_of(&words)` 순서로 호출하고, 단어 벡터를 복사하지 않는다 |

`merge`, `drop_rare`, `longer`, `main.rs` 는 바꾸지 않았다.

### 동작이 같다고 본 근거 (normalize 의 순서 변경)

Python 은 `lower()` 를 먼저 하고 `strip(string.punctuation)` 을 한다. 새 구현은 trim 을 먼저 한다. 두 순서의 결과가 같은 이유는 다음과 같다.
- 소문자 변환은 ASCII 문장부호를 만들지도 바꾸지도 않는다. 그래서 떼어 낼 범위가 같다.
- 문맥을 보는 변환은 그리스어 끝 시그마(Σ→ς) 하나다. 떼어 내는 글자는 단어 맨 앞이나 맨 뒤의 cased 가 아닌 글자뿐이라서, Σ 앞뒤에 cased 글자가 있는지는 바뀌지 않는다.
- 빌려 쓸지 정하는 조건(`to_lowercase()` 가 그 글자 자신 하나인지)은 대문자뿐 아니라 titlecase(ǅ), İ, Kelvin 기호(K)처럼 변환되는 글자도 모두 잡는다.

직접 확인한 것: `target/uni_input.txt`(ΟΔΟΣ. ΑΣ! ǅemal İstanbul K Straße ﬀ ÉLAN 등)를 Rust 바이너리에 넣어 보니 `οδος`, `ας`, `ǆemal`, `i̇stanbul`, `k` 처럼 기대한 출력이 나왔다.
**같은 입력으로 Python 기준 구현을 돌리는 것은 실행 권한이 승인되지 않아 하지 못했다.** 그래서 Python 과의 바이트 단위 비교는 이 입력에 대해서는 검증하지 않았다. 확인한 것은 `tests/spec.rs` 의 기대값뿐이다.

## 2. 세 검사의 마지막 실행 결과 (직접 실행)

- `cargo fmt --check` — 출력 없음, 통과
- `cargo clippy --all-targets -- -D warnings` — 경고 없이 `Finished`, 통과
- `cargo test` — `tests/spec.rs` 11 passed, 0 failed (lib/main/doc 테스트는 0개), 통과

## 3. 고치지 못한 것 / 남은 것

- 공개 `longest` 는 `&[String]` 그대로 두었다. 테스트의 `longest(&[])` 때문에 제네릭으로 바꿀 수 없다. 그래서 `Cow` 벡터에서는 이 함수를 바로 쓸 수 없다(crate 안에서는 `longest_of` 를 쓴다).
- `count` 반환 맵의 키는 계속 `String` 이다. 테스트가 `HashMap<String, usize>` 를 요구하기 때문이다. 대신 서로 다른 단어 하나당 한 번만 만든다.
- 테스트가 Python 기준 구현과 어긋나는 곳은 찾지 못했다.
