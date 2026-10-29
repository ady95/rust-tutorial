rust_app/ 의 HTTP 서버 계층을 axum 과 tokio 로 바꿔 주세요. 동작(응답)은 바꾸지 않습니다.

지금 구현은 외부 크레이트 없이 std 로 HTTP/1.1 을 직접 처리합니다(http.rs, main.rs 등). 이 부분을 axum(내부적으로 hyper)과 tokio 런타임으로 바꿉니다.

- crates.io 접속이 허용되어 있으니 cargo add 로 axum, tokio 등을 추가하세요
- 라우팅·검증·응답 형식(router.rs, handlers.rs, lax.rs, pyjson.rs, jsonout.rs 등)은 그대로 써도 됩니다.
  계약의 경로 규칙(307 리디렉션, 처음 등록된 라우트의 Allow, HEAD 미처리, 원래 경로 문자열 기준 판정)을 axum 의 라우터로 맞추기 어렵다면
  axum 의 fallback 처리기 하나로 모든 요청을 받아 기존 라우터에 넘기는 방식도 좋습니다
- 상태 공유는 tokio 의 여러 작업자 스레드에서 안전해야 하고, reserve 의 확인과 차감은 원자적이어야 합니다(계약 5절)
- 명령행(--host, --port)과 종료 코드는 그대로입니다
- 완료 조건(fmt, clippy, test, release 빌드, automation/port.json 의 비교 도구)을 직접 실행해 확인하세요

끝나면 reports/variant_notes.md 에 바꾼 구조, 추가한 크레이트와 이유, 확인한 것을 짧게 적어 주세요.
