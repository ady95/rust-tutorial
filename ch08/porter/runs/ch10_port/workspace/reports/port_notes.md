# stockroom Rust 이식 노트

- 위치: `rust_app/` (바이너리 `stockroom`, 외부 크레이트 없음: std 만 사용)
- 구성: `main.rs`(인자) · `http.rs`(HTTP/1.1, 연결마다 스레드) · `router.rs`(라우팅·unquote·parse_qsl·307 Location)
  · `pyjson.rs`(json.loads 호환) · `lax.rs`(pydantic lax 변환) · `models.rs`(검증) · `store.rs` · `handlers.rs` · `jsonout.rs`
  · `verify_io.rs`(검증 전용, `#[ignore]` 테스트로만 돈다)
- port/plan.json 의 권장(hyper/tokio/ryu)과 달리 의존성 없이 std 로 짰다. 네트워크 없는 샌드박스에서도 빌드되게 하려는 것이다.

## 1. 특별히 처리한 Python 동작

**HTTP(uvicorn + h11 0.16)** — 모두 원시 소켓으로 기준 서버와 대조했다(2절)
- 요청 줄과 헤더를 h11 규칙으로 검사한다. 어기면 400 `Invalid HTTP request received.` 을 보내고 연결을 닫는다.
- HTTP/1.1 이상은 Host 헤더가 정확히 하나여야 한다. Host 가 둘 이상이면 버전과 상관없이 400 이다.
- HTTP/1.0 은 응답 뒤 연결을 닫는다. HTTP/1.1 이상(`HTTP/2.0`, `HTTP/1.2` 포함)은 keep-alive 다.
- obs-fold(줄이 공백으로 시작)는 앞 헤더 값에 공백 하나로 이어 붙인다. 첫 헤더에서 쓰면 400 이다.
- `Content-Length` 의 쉼표 목록은 값이 모두 같을 때만 받는다. `Transfer-Encoding: chunked` 가 있으면 `Content-Length` 는 무시한다.
- chunked 조각 뒤에는 정확히 CRLF 가 와야 한다.
  - 본문 단계 오류는 400 을 chunked 로 보낸다.
  - 헤더 단계 오류는 content-length 없이 보내고 연결을 닫는다(기준과 같음).
- `Expect: 100-continue` 이면 본문을 읽는 라우트에서만 `100 Continue` 를 먼저 보낸다.
- 요청 머리 한도는 실측한 127973 바이트다(요청 줄부터 빈 줄까지, CRLF 포함).

**라우팅(Starlette 1.10)**
- 경로를 `unquote(errors="replace")` 와 같게 디코딩한 뒤 라우팅한다. Python `$` 처럼 끝의 `\n` 하나를 허용한다.
- 405 의 Allow 는 경로가 맞은 첫 라우트의 메서드 하나다.
- 307: 끝의 `/` 를 모두 떼고 다시 맞춘다. Location 의 Host 는 `parse_host_header` 규칙을 따르고, 경로 `?#\` 는 퍼센트 인코딩한 뒤 `quote(safe=...)` 를 적용한다.
- 쿼리는 `parse_qsl(latin-1, keep_blank_values=True)` 와 같게 해석하고, 같은 이름이 여러 번이면 마지막 값을 쓴다.

**본문(FastAPI 0.162)**
- 본문 라우트만 본문을 해석한다. json_invalid 와 400 은 경로·쿼리 검증보다 먼저 응답한다. 빈 본문은 `missing` 이다.
- Content-Type 이 없거나 비어 있으면 `model_attributes_type` 이다. 판정은 email.message 와 같다(Python strip 공백 집합, 소문자화, `/` 정확히 1개).
- `json.loads(bytes)`:
  - 인코딩: `detect_encoding` 으로 가리고 `surrogatepass` 로 디코딩한다. 실패하면 400.
  - 스캐너: `_json.c` 의 오류 위치(코드 포인트 단위), NaN/Infinity, 4300자리를 넘는 정수는 400, 중복 키는 첫 위치에 뒤 값.
  - 중첩 한도: 9993단계를 넘으면 400(RecursionError). 스레드 스택 64MB 로 이 깊이를 견딘다.

**pydantic-core 2.50 lax**
- 문자열→정수 규칙(`lax::str_as_int`):
  1. 원문에 JSON 정수 문법을 먼저 적용한다. 4300자를 넘으면 `int_parsing_size` 다.
  2. 그다음 Rust `trim()` 을 하고, 부호 → 앞의 0·밑줄 → 밑줄 → JSON 정수 순으로 본다. `.0+` 접미는 떼고 다시 시도한다.
- 문자열→실수: `trim().parse::<f64>()`, 실패하면 원문의 밑줄을 뗀다(앞·뒤 밑줄이나 `__` 가 있으면 `float_parsing`).
- 실수→정수: |x| ≥ 2^63 이면 `int_parsing_size`. 정수→실수: 넘치면 `float_type`.
- 제약 검사는 le 를 먼저 본다(NaN·inf → less_than_equal).
- 문자열의 고립 서로게이트는 `string_unicode` 다. 키 하나라도 서로게이트면 `string_unicode` 하나(loc `["body"]`)만 낸다.
- tags 가 10개를 넘으면 원소 오류를 버리고 `too_long` 하나만 낸다. 필드 순서 뒤에 입력 키 순서로 extra_forbidden 이 온다.

**응답**
- 실수 표기는 ryu 배치 규칙이고 자릿수는 최단 왕복이다.
  - 같은 길이 후보가 정확히 반반이면 짝수 쪽을 고른다(pydantic-core 실측. Rust `{:e}` 는 위로 올리므로 같은 자릿수의 정확 반올림으로 다시 만든다).
  - 양수 지수에는 `+` 를 붙이지 않는다(계약 4절. 3절 1번 참고).
- stats `total_value` 는 CPython `sum()` 의 Neumaier 보정 합산이고, 빈 저장소면 정수 `0` 이다.
- 404 의 id 는 정규화한 정수 문자열이다. reserve 의 확인·차감은 Mutex 가드 하나 안에서 끝낸다.
- 명령행은 argparse 를 흉내 낸다.
  - 접두 약어, `=` 형식, 모호하면 `could match ...`, 인식 못 한 인자는 모아서 한 번에 보고, `--help` 전체 문구.
  - `--port` 는 Python `int()`(공백, 부호, 밑줄)로 읽는다.
  - 범위 밖 포트는 종료 코드 1, 바인드 실패는 종료 코드 3 이다(uvicorn 과 같은 문구 형식).

## 2. 직접 실행해 확인한 것

| 명령 | 결과 |
|---|---|
| `cargo fmt --check` · `cargo clippy --all-targets -- -D warnings` · `cargo build --release` | 통과 |
| `cargo test` | 14 통과(검증용 1개는 ignored) |
| `automation/compare.py` | 20/20 |
| `automation/fuzz.py --examples 400 --seed 7`(이전 실행: seed 없이 400, `--seed 20261029` 400, 1500) | 모두 match |
| `verify/diff_extra.py`(plan 위험 항목의 추가 입력) | 문서 라우트 1건(3절 2번)만 다름 |
| `verify/diff_ints.py 3000`, `verify/concurrency.py` | 모두 같음 / 1000건 성공·600건 409·남은 수량 0 |

**지난 보고서 3절 항목을 실행으로 확인한 결과** (`verify/exhaustive.py gen` → `cargo test --release -- --ignored dump_for_verify` → `verify/exhaustive.py check`. Rust 함수의 결과를 기준 Python 함수와 한 줄씩 비교한다)

| 항목 | 입력 공간 | 결과 |
|---|---|---|
| 문자열→정수 (pydantic `TypeAdapter(int)`) | **모든 코드 포인트**(서로게이트 제외, 1,112,064개) × 템플릿 6개 = 6,672,384 + 무작위·4300자 경계 178,601 | 모두 같음 |
| 문자열→실수 (`TypeAdapter(float)`) | 모든 코드 포인트 × 템플릿 6개 + 무작위 178,601 | 모두 같음 |
| 퍼센트 디코딩 (`urllib.parse.unquote`) | **1·2바이트 전부**, 3바이트(대표 바이트 71종의 모든 조합), 4바이트 일부, 무작위 % 조합: 582,976 | 모두 같음 |
| json 인코딩 감지 + surrogatepass | 대표 바이트 19종의 1~4바이트 전부 + 무작위 5~12바이트: 337,560 | 모두 같음 |
| json.loads 오류 위치·종류 | JSON 조각 무작위 조합 239,093(UTF-16 포함) | 모두 같음 |
| Content-Type 판정 (email.message) | **latin-1 바이트 전부**(h11 이 막는 5개 제외) × 위치 9가지 + 무작위: 28,221 | 모두 같음 |
| Host 판정 (Starlette `parse_host_header`, IPv6 포함) | latin-1 바이트 전부 × 2 + IPv6 표기 23종 × 포트 6종 + 무작위: 138,637 | 모두 같음 |
| 실수 표기 (`pydantic_core.to_json`) | 무작위 비트 패턴 100만 + [0,1e6] 40만 + 10^e·2^k 경계와 그 이웃, 비정규수: 1,410,175 | **반반 경우 221개가 달랐다 → 고쳤다.** 이제는 양수 지수의 `+` 만 다르다(3절 1번) |
| JSON 중첩 한도 (`verify/probe_depth.py`) | POST /items, PATCH, reserve × 배열·객체 | 셋 다 기준 9992 = Rust 9992, 그다음 깊이는 둘 다 400 |
| HTTP 계층 (`verify/http_raw.py`, 원시 소켓) | 요청 target·첫 바이트·헤더 값·헤더 이름·메서드에 **0~255 바이트 전부**(1280건) + 특수 69건(버전, Host 없음·중복, obs-fold, chunked·확장·트레일러·잘못된 조각, TE+CL, CL 목록·부호·16진, Expect, HEAD, 파이프라이닝, 머리 크기 경계, 1MB·5MB 본문) | **Host·버전·obs-fold·chunked footer·CL 목록·Expect·머리 한도에서 차이를 찾아 고쳤다.** 이제 1348/1349 같다. 나머지 1건은 비교 대상이 아닌 `date`/`server` 헤더 차이뿐이다 |
| 요청 머리 한도 (`verify/probe_head_limit.py`) | 70000~200000 이분 탐색, 두 번 측정 | 기준은 두 번 다 127933(값 길이), Rust 도 같은 경계 |
| 명령행 (`verify/cli.py`) | 30가지 인자 | 27/30 같다. 차이는 3절 4번 |
| stats 1e16 (`verify/stats_big.py`) | 1e12 × 10000개 | 9999개는 같다. 10000개는 3절 1번 |

## 3. 사람이 정할 일 / 남은 차이

1. **계약과 기준 구현이 다르다: 양수 지수의 `+`.**
   - 계약 4절은 "지수에 `+` 없음"이라고 적었다. 기준 구현(pydantic-core)은 `1e+16`, `2.79e+289` 처럼 `+` 를 붙인다.
   - 이 API 에서 영향을 받는 곳은 stats 의 `total_value` 가 1e16 이상일 때뿐이다(price ≤ 1e6 이라 Item 에서는 나오지 않는다).
   - 실측: 1e12 짜리 Item 10000개로 기준 `"total_value":1e+16`, Rust `1e16`.
   - 지시에 따라 고치지 않고 계약 쪽(`+` 없음)을 유지했다. 기준에 맞추려면 `jsonout::push_f64` 의 두 지수 분기에서 양수일 때 `+` 를 넣으면 된다.
2. **계약과 기준 구현이 다르다: FastAPI 기본 문서 라우트.**
   - 기준에는 `/openapi.json`, `/docs`, `/docs/oauth2-redirect`, `/redoc` 가 있고(`/openapi.json/` → 307 등), 계약 2절의 표에는 없다.
   - Rust 는 404 다. 정하는 대로 따르겠다.
3. **확인하지 않은 범위.**
   - 실수 표기는 f64 전체(2^64)를 전수하지 않고 141만 개 표본과 경계값만 봤다.
   - 문자열→정수/실수는 코드 포인트 하나씩은 전수했지만, 여러 문자의 모든 조합은 무작위 표본이다.
   - 요청 머리 한도 127973 은 h11/uvicorn 의 읽기 단위에서 나온 값으로 보인다. 이 기계에서 두 번 같게 나왔지만, 원인 규칙을 소스로 밝히지는 못했다. TCP 분할이 달라지면 기준 쪽 경계가 달라질 수 있다.
4. **명령행 차이(고치지 않음).**
   - `--port ٣` 같은 비ASCII 숫자: Python `int()` 는 받는다(포트 3). Rust 는 ASCII 숫자만 받아 종료 코드 2 를 낸다. Unicode Nd 숫자표를 std 만으로 넣기에는 비용이 커서 남겼다.
   - `--port 99999` / `-1`: 종료 코드(1)는 같다. 기준은 uvicorn 의 Python traceback 을 stderr 에 내고, Rust 는 한 줄 메시지를 낸다.
5. `uv run` 이 `VIRTUAL_ENV` 경로 불일치 경고를 내지만 결과에는 영향이 없었다. automation/·tests/·python_src/ 는 수정하지 않았다.
