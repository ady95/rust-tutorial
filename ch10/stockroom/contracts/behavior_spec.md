# stockroom 동작 계약 (behavior spec)

기준 구현: `python_src/stockroom/app.py` (승인일 2026-10-29, FastAPI 0.162, pydantic 2.14, Starlette 1.10, uvicorn, Python 3.12)
같은 날 4절의 실수 지수 표기 문구를 정정했다(처음 승인한 문구 "지수에 `+` 없음"은 확인하지 않고 쓴 것으로, 이식 에이전트의 후속 확인이 기준 구현과 다름을 찾았다).
다른 언어로 재구현할 때 아래 항목이 같아야 한다. "비교 안 함"으로 적힌 항목만 예외다.
이 문서의 예는 모두 기준 구현으로 실행해 확인한 것이다.

## 1. 실행

```
stockroom [--host HOST] [--port PORT]      # 기본 127.0.0.1, 8000
```

- HTTP/1.1. 상태는 메모리에만 있고 프로세스가 끝나면 사라진다
- 환경 변수 `STOCKROOM_TEST=1`이면 `POST /_test/reset`(204, 본문 없음)으로 상태를 처음으로 되돌린다(id도 1부터). 그 밖에는 이 경로가 없다(404)
- 기준 구현은 `python python_src/run_server.py`로 띄운다(uvicorn 작업자 1개)

## 2. 엔드포인트

| 메서드 | 경로 | 성공 | 본문 |
|---|---|---|---|
| GET | `/health` | 200 | `{"status":"ok"}` |
| POST | `/items` | 201, `Location: /items/<id>` | 만든 Item |
| GET | `/items?limit=&offset=&tag=` | 200 | `{"items":[Item...],"total":<태그 조건에 맞는 전체 수>}` |
| GET | `/items/{item_id}` | 200 | Item |
| PATCH | `/items/{item_id}` | 200 | 바뀐 Item |
| DELETE | `/items/{item_id}` | 204 | 없음 |
| POST | `/items/{item_id}/reserve` | 200 | `{"item_id":<id>,"reserved":<n>,"remaining":<n>}` |
| GET | `/stats` | 200 | `{"items":<수>,"total_quantity":<합>,"total_value":<합>}` |

Item: `{"id":<int>,"name":<str>,"price":<float>,"quantity":<int>,"tags":[<str>...]}` (키 순서 그대로)

- id는 1부터 하나씩 늘고 지운 id를 다시 쓰지 않는다
- 목록은 id 오름차순. `tag`가 있으면 그 태그를 가진 것만. `offset`개를 건너뛰고 `limit`개
- PATCH는 보낸 필드만 바꾼다. 빈 객체 `{}`는 아무것도 바꾸지 않고 200
- reserve는 `quantity`가 남은 수량보다 크면 409, 아니면 수량을 줄인다
- stats의 `total_value`는 모든 Item의 `price * quantity`를 id 순서로 Python `sum()`(오차 보정 합산, 07-4)한 값

## 3. 요청 해석

### 3.1 경로와 메서드

- 경로는 대소문자를 구분하고 정확히 일치해야 한다(`/Items`, `/items//1`은 404)
- 일치하는 경로가 없을 때 경로가 `/`로 끝나고, 끝의 `/`를 뗀 경로가 어떤 라우트와 일치하면(메서드 무관) **307**: 본문 없음, `Location: http://<요청의 Host 헤더><뗀 경로>[?<원래 쿼리>]`
- 그 밖에 일치하는 경로가 없으면 404 `{"detail":"Not Found"}`
- 경로는 있지만 메서드가 없으면 405 `{"detail":"Method Not Allowed"}`, `Allow` 헤더는 그 경로에 처음 등록된 라우트의 메서드 하나: `/health` GET, `/items` POST, `/items/{item_id}` GET, `/items/{item_id}/reserve` POST, `/stats` GET, `/_test/reset` POST. HEAD·OPTIONS도 따로 처리하지 않는다(405)

### 3.2 정수(경로의 item_id, 쿼리의 limit·offset)

pydantic 2.14의 느슨한(lax) 정수 해석을 따른다. 확인한 예:

| 받음 | 거부(`int_parsing`) |
|---|---|
| `5`, `05`, `+1`, `-1`, `-0`, ` 5 `(앞뒤 공백), `5_0`(=50), `5.0`, 20자리 수 | `5.5`, `1e1`, `0x1`, `true`, 빈 문자열, `+-1`, 비ASCII 숫자(`٥`, `１`) |

- item_id는 크기 제한이 없다(`99999999999999999999`는 404 `item 99999999999999999999 not found`)
- 같은 쿼리 이름이 여러 번 오면 마지막 값. `tag=`(빈 값)은 빈 문자열 태그
- limit: 1~100(`greater_than_equal`/`less_than_equal`), offset: 0 이상

### 3.3 본문

- Content-Type의 미디어 타입이 `application/json`이거나 `+json`으로 끝나면(`application/vnd.api+json`) JSON으로 해석한다. 매개변수(`; charset=utf-8`)는 무시
- 본문이 비어 있으면 `missing`(loc `["body"]`)
- 본문이 UTF-8이 아니면 400 `{"detail":"There was an error parsing the body"}`
- Content-Type이 없거나 JSON이 아니면 본문은 문자열로 취급되어 `model_attributes_type`(loc `["body"]`)
- JSON은 Python `json.loads`로 해석한다: `NaN`·`Infinity` 리터럴을 받고, 같은 키는 뒤의 값. 해석 오류는 `json_invalid`, loc `["body", <오류 위치>]`(Python `JSONDecodeError.pos`, 문자 단위)
- 객체가 아니면(`null`, 배열 등) `model_attributes_type`(loc `["body"]`)

### 3.4 본문 필드(pydantic 2.14 lax)

| 필드 | 규칙 | 받는 예 | 오류 type |
|---|---|---|---|
| name | 문자열, 1~100자(코드 포인트) | | `string_type`, `string_too_short`, `string_too_long` |
| price | 실수 0~1,000,000 | 숫자, `true`(1.0), 문자열 `"12.5"`, `" 2 "`, `"1_0.5"`, `"1e-5"` | `float_type`(null 등), `float_parsing`(`"true"`, `"0x1p3"`), `greater_than_equal`, `less_than_equal`(NaN·Infinity·`"inf"`·`"nan"`·`1e400`도 여기) |
| quantity | 정수 0~1,000,000 | 정수, `true`/`false`, `3.0`, 문자열 `"3"`, `" 3"`, `"3.0"`, `"1_0"` | `int_type`, `int_parsing`(`"true"`, `"1e3"`), `int_from_float`(3.5), `greater_than_equal`, `less_than_equal` |
| tags | 문자열 목록, 최대 10개, 각 1~20자 | | `list_type`, `too_long`, `string_type`(loc에 인덱스), `string_too_short`, `string_too_long` |
| (그 밖의 키) | 허용 안 함 | | `extra_forbidden` |
| reserve.quantity | 정수 1~1,000,000 | quantity와 같음 | quantity와 같고 하한은 `greater_than` |

- POST의 필수 필드가 없으면 `missing`. tags는 생략하면 `[]`
- PATCH의 필드는 모두 선택. 값이 `null`인 필드가 있으면 400 `{"detail":"fields cannot be null"}`

### 3.5 판정 순서

1. 경로·메서드(3.1)
2. 검증: 경로 매개변수 → 쿼리 → 본문 순으로 오류를 모아 하나라도 있으면 422(존재 여부보다 먼저. `PATCH /items/99`에 잘못된 본문이면 404가 아니라 422)
3. 처리: 없는 id는 404 `{"detail":"item <id> not found"}`, PATCH의 null은 400, reserve의 부족은 409 `{"detail":"insufficient stock: requested <n>, available <m>"}`

## 4. 응답과 비교 규칙

| 항목 | 비교 |
|---|---|
| 상태 코드 | 같아야 함 |
| `Content-Type` | 같아야 함(JSON은 `application/json`, 204·307은 없음) |
| `Location`(201, 307), `Allow`(405) | 같아야 함 |
| 그 밖의 헤더(`server`, `date`, `content-length` 등) | 비교 안 함 |
| 본문(422 제외) | 바이트 단위로 같아야 함 |
| 422 본문 | `{"detail":[{"type":..,"loc":[..],"msg":..}, ...]}`. **type과 loc의 목록(순서 포함)만 비교**, msg는 비교 안 함 |

- JSON은 공백 없는 한 줄, ASCII가 아닌 글자는 이스케이프하지 않는다
- 실수(price, total_value)의 표기는 pydantic-core와 같다: `1.0`, `12.5`, `0.00001`, `1e-7`, `5e-324`, `999999.9999999999`(가장 짧은 왕복 표기, 지수 범위에 따라 소수 또는 지수 형식. 음수 지수는 `1e-7`, 양수 지수는 `1e+16`처럼 `+`를 붙인다. `total_value`가 1e16 이상일 때 나온다)
- 정수 필드(id, quantity, total_quantity 등)는 정수로

## 5. 동시성

- 요청은 동시에 들어올 수 있다. reserve의 확인과 차감은 원자적이어야 한다(같은 Item에 대한 동시 예약의 합이 처음 수량을 넘지 않는다)
- 기준 구현은 이벤트 루프 하나에서 `async` 처리 함수 안에 `await` 없이 확인과 차감을 하므로 원자적이다
