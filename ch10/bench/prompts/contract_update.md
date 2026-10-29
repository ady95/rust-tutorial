사람이 계약(contracts/behavior_spec.md)을 갱신했습니다. rust_app/ 을 새 계약에 맞춰 주세요. 계약 맨 위와 각 절에 2026-10-30 갱신 내용이 있습니다.

바뀐 것:
- 4절: 실수의 양수 지수는 `1e+16` 처럼 `+` 를 붙인다(이전 계약은 "`+` 없음"이었고, 지금 구현은 그 문구를 따른다)
- 2절: API 문서 경로(/docs, /redoc, /openapi.json, /docs/oauth2-redirect)는 없다(404). 지금 구현도 404 일 것이다
- 3.6절(새로 생김): 잘못된 HTTP 요청은 기준 구현과 같은 상태 코드이거나 4xx 이면 되고 본문은 비교하지 않는다. 단 Host 헤더가 없거나 두 개 이상인 HTTP/1.1 요청은 400 이어야 한다
- 5절: 동시성 시험 automation/race.py 가 게이트에 들어갔다

tests/cases.json 에 이 규칙을 시험하는 케이스(stats-exponent, docs-disabled, malformed-http)가 추가되었습니다.
완료 조건(fmt, clippy, test, release 빌드, automation/port.json 의 compare·fuzz·race)을 직접 실행해 확인하고, reports/variant_notes.md 에 바꾼 것을 짧게 적어 주세요.
