# variant_notes: HTTP 계층을 axum + tokio 로 교체

## 바꾼 구조
- `http.rs`: 직접 만든 HTTP/1.1 파서·스레드 서버를 지우고, axum `Router` 의 `fallback` 처리기 하나가 모든 요청을 받아 기존 `App::handle`(router.rs / handlers.rs 등)에 넘긴다. 307, Allow, HEAD 미처리, 원래 경로 문자열 기준 판정은 axum 라우터를 쓰지 않고 기존 `router.rs` 가 그대로 판정한다.
- 요청 대상은 `uri.path_and_query()` 문자열, 헤더는 (소문자 이름, 값 바이트) 로 변환해 넘긴다. 본문은 `DefaultBodyLimit::disable()` 후 전부 읽는다. 로컬 주소(Location 용)는 `Connected` 구현으로 연결의 `local_addr()` 를 받는다.
- `main.rs`: 인자 처리와 종료 코드(2, 1, 3)는 그대로. 바인드는 기존처럼 std `TcpListener` 로 하고(오류 메시지·코드 유지) tokio 리스너로 변환해 멀티스레드 런타임에서 `axum::serve` 한다. JSON 재귀 해석 때문에 작업자 스레드 스택을 64MiB 로 늘렸다(`thread_stack_size`).
- 상태 공유: 기존 `Mutex<Store>` 를 `Arc<App>` 로 공유한다. 처리 함수가 동기·`await` 없이 락 안에서 확인과 차감을 하므로 여러 작업자 스레드에서도 reserve 는 원자적이다. 패닉은 `catch_unwind` 로 500 처리(기존과 동일).
- 지운 것: `App::reads_body`(100 Continue 판단용; 이제 hyper 가 처리).

## 추가한 크레이트
- `axum` 0.8: HTTP 서버 계층(내부적으로 hyper). 기본 기능 그대로.
- `tokio` 1 (`rt-multi-thread`, `net`, `macros`): 멀티스레드 런타임과 비동기 TCP.

## 확인한 것 (직접 실행)
- `cargo fmt`, `cargo clippy --all-targets -- -D warnings`, `cargo test`(14 통과, 1 ignored), `cargo build --release` 모두 통과.
- `automation/compare.py`: 20/20 일치. `automation/fuzz.py --examples 400 --seed 7341`: 일치.

## 확신하지 못하는 부분 / 달라진 점
`verify/probe_axum_raw.py` 로 확인한 결과, hyper 가 HTTP 파싱을 맡으면서 비교 도구가 다루지 않는 저수준 동작이 이전 직접 구현(h11 규칙을 맞춘 것)과 달라졌다. 응답 본문·상태 코드를 다루는 비교 도구는 통과하지만 아래는 **기준과 다를 수 있다**.
- 응답에 `date` 헤더가 붙는다(이전에는 없었음). 기준 uvicorn 이 보내는 헤더 집합과의 일치는 확인하지 않았다.
- `Host` 없는 HTTP/1.1 요청이 200 으로 처리된다(이전: h11 처럼 400).
- 잘못된 요청 줄은 400 이지만 본문이 비어 있다(이전: `Invalid HTTP request received.`).
- 머리 크기 한도(127973 바이트), 헤더 접기, `Content-Length` 쉼표 목록, chunked 세부 오류, `Expect: 100-continue` 를 라우트별로 구분하던 동작은 hyper 기본 동작으로 바뀌었고 개별 검증하지 않았다.
이 차이를 맞추려면 hyper 앞에 별도 검사 계층이 필요해 이번 범위에서는 하지 않았다.
