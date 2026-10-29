# logstat 동작 계약 (behavior spec)

기준 구현: `python_src/logstat.py` (승인일 2026-10-29, Python 3.12. 같은 날 3절 ts 오프셋 문구 정정: 08장 파이프라인의 분석 단계 지적)
2026-10-30: 4절에 서로게이트 경로 출력 규칙, 2.2절에 깊이 한도의 기준(CLI 실행)을 더했다(09-2에서 사람의 결정으로 남긴 항목).
다른 언어로 재구현할 때 아래 항목은 바이트 단위로 같아야 한다. "비교 안 함"으로 적힌 항목만 예외다.

## 1. 명령행

```
logstat FILE [--format csv|jsonl] [--top N] [--json] [--strict]
```

| 인자 | 의미 | 기본값 |
|---|---|---|
| `FILE` | 읽을 로그 파일 (필수) | |
| `--format` | 입력 형식. 없으면 파일 이름 끝(대소문자 무시)으로 정한다: `.csv` → csv, `.jsonl`·`.ndjson` → jsonl. 둘 다 아니면 인자 오류 | |
| `--top N` | 출력할 상위 경로 수. ASCII 숫자만, 1 이상 | 10 |
| `--json` | 텍스트 대신 JSON 한 줄 | 꺼짐 |
| `--strict` | 잘못된 레코드를 만나면 그 자리에서 오류로 끝냄 | 꺼짐 |

옵션 이름 줄여 쓰기(`--fo`)는 받지 않는다.

## 2. 입력

파일 전체를 바이트로 읽어 UTF-8로 해석한다. BOM은 떼지 않는다(그래서 BOM이 붙은 CSV는 첫 열 이름이 `ts`가 아니게 된다).

### 2.1 CSV

- Python `csv.reader` 기본 방언(excel)과 같은 규칙: 쉼표 구분, 큰따옴표 인용, 인용 안의 `""`는 `"`, 인용 안의 줄바꿈 허용, 줄 끝 `\n`·`\r\n`·`\r`
- 첫 행은 헤더. 열 순서는 자유이고 여분의 열은 무시한다. 같은 이름이 두 번 나오면 뒤의 열을 쓴다
- 필수 열(`ts`, `method`, `path`, `status`, `bytes`, `latency_ms`)이 헤더에 없으면 입력 오류: `missing column: <이름>`(필수 열 순서대로 처음 빠진 것)
- 빈 행은 건너뛰고 레코드 번호도 세지 않는다
- 필드 수가 헤더와 다르면 그 레코드는 `bad field count`
- 필드 하나가 131,072자보다 길면 파일 전체를 거부한다(입력 오류): 헤더면 `header: csv field too large`, 아니면 `record <N>: csv field too large`
- 파일이 비어 있으면 레코드 0개

### 2.2 JSON Lines

- `\n`으로만 줄을 나눈다. 공백·`\t`·`\r`만 있는 줄은 건너뛰고 레코드 번호도 세지 않는다
- 각 줄은 Python `json.loads`로 해석한다(`NaN`, `Infinity` 리터럴을 받고, 같은 키가 두 번 나오면 뒤의 값). 해석할 수 없으면 `invalid json`, 객체가 아니면 `not an object`
- Python의 한계도 그대로 따른다: 4,300자리가 넘는 정수 리터럴(앞의 `-` 제외)이 있으면 `invalid json`, 배열·객체의 중첩 깊이(바깥 객체 포함)가 9,997을 넘으면 `invalid json`(Python 3.12.3에서 측정한 재귀 한도). 이 값은 CLI로 실행했을 때의 한도이며, 기준 구현의 함수를 다른 C 함수의 콜백 안에서 부를 때 줄어드는 한도는 따르지 않는다
- 필수 키가 없으면 `missing field: <이름>`(필수 열 순서대로 처음 빠진 것). 여분의 키는 무시한다

## 3. 필드 규칙

검사 순서는 CSV는 method → status → bytes → latency_ms → ts → path, JSON은 키 존재 → method → status → bytes → latency_ms → ts → path이다. 처음 어긴 규칙이 그 레코드의 이유가 된다.

| 필드 | CSV(문자열) | JSON | 이유 문자열 |
|---|---|---|---|
| method | `GET POST PUT DELETE PATCH HEAD OPTIONS` 중 하나(대소문자 구분) | 같음(문자열) | `bad method` |
| status | 정규식 `[1-5][0-9]{2}` 전체 일치 | 정수(불리언·실수 불가), 100~599 | `bad status` |
| bytes | `[0-9]+` 전체 일치, 값 0~10^12 | 정수, 0~10^12 | `bad bytes` |
| latency_ms | `[0-9]+(\.[0-9]+)?` 전체 일치, 실수로 바꾼 값이 10^9 이하 | 정수 또는 실수(불리언 불가), 0~10^9, NaN 불가 | `bad latency_ms` |
| ts | `YYYY-MM-DDTHH:MM:SS`, 선택적 소수부 1~6자리, `Z` 또는 `±HH:MM`. 숫자는 ASCII만. 실제 존재하는 날짜·시각이어야 하고(윤초 불가, 24시 불가), 오프셋의 분은 두 자리면 59를 넘어도 되지만(`+00:60`은 1시간, `+00:99`는 1시간 39분) 오프셋 전체가 24시간 미만, UTC로 바꾼 값이 1~9999년 안 | 같음(문자열) | `bad ts` |
| path | `/`로 시작. 첫 `?`부터 끝까지(쿼리)는 버린다 | 같음(문자열) | `bad path` |

`--strict`가 아니면 규칙을 어긴 레코드는 버리고 `skipped`에 센다.

## 4. 오류

| 상황 | stderr | 종료 코드 |
|---|---|---|
| 파일 없음 | `logstat: error: file not found: <FILE>` | 1 |
| 그 밖의 읽기 실패 | `logstat: error: cannot read file: <FILE>` | 1 |
| UTF-8이 아님 | `logstat: error: not valid UTF-8: <FILE>` | 1 |
| CSV 헤더 오류, 너무 긴 필드 | `logstat: error: <2.1의 메시지>` | 1 |
| `--strict`에서 잘못된 레코드 | `logstat: error: record <N>: <이유 문자열>` (N은 1부터, 2절의 레코드 번호) | 1 |
| 인자 오류 | 비교 안 함(비어 있지만 않으면 됨) | 2 |
| 출력할 경로(top_paths)에 짝 없는 서로게이트가 있음(JSON의 `"\ud800"` 등) | 비교 안 함 | 1 |

오류일 때 stdout은 비어 있어야 한다. `<FILE>`이 UTF-8이 아니면 stderr 내용은 비교하지 않는다.

## 5. 출력 (종료 코드 0, UTF-8, 줄바꿈 LF)

집계 대상은 규칙을 통과한 레코드다.

| 항목 | 정의 |
|---|---|
| records, skipped | 통과한 레코드 수, 버린 레코드 수 |
| first, last | ts의 최솟값·최댓값을 UTC로 바꿔 Python `datetime.isoformat()` 형식으로: `YYYY-MM-DDTHH:MM:SS+00:00`, 마이크로초가 0이 아니면 `.ffffff`(6자리)를 초 뒤에 |
| bytes | bytes의 정확한 합(넘침 없이) |
| status | `2xx 3xx 4xx 5xx` 순서의 개수(1xx는 어디에도 세지 않음) |
| methods | 메서드별 개수. 개수 내림차순, 같으면 이름 오름차순. 0개인 메서드는 없음 |
| latency_ms p50, p95, p99 | 전체 latency_ms의 nearest-rank 백분위수: 오름차순 정렬 후 `ceil(p × n / 100)`번째(1부터) 값 |
| peak_minute | UTC 분(`YYYY-MM-DDTHH:MMZ`)별 레코드 수가 가장 많은 분. 같으면 이른 분 |
| top_paths | 경로별 개수 내림차순, 같으면 경로의 코드 포인트 오름차순으로 상위 N개. 각 항목은 개수, 오류율, p50, p95 |
| 오류율 | 그 경로에서 status ≥ 500 인 비율 × 100을 소수 첫째 자리로(Python `f"{x:.1f}"`) + `%` |

실수(latency 값, 백분위수)의 표기는 Python `repr(float)`과 같다(예: `1.5`, `12.0`, `1e-05`).

텍스트 형식:

```
records: <n>
skipped: <n>
range: <first> .. <last>
bytes: <n>
status: 2xx=<n> 3xx=<n> 4xx=<n> 5xx=<n>
methods: <M>=<n> <M>=<n> ...
latency_ms: p50=<x> p95=<x> p99=<x>
peak_minute: <minute> <n>
top_paths:
<count>\t<오류율>\t<p50>\t<p95>\t<path>
```

레코드가 0개면 `range: -`, `methods: -`, `latency_ms: -`, `peak_minute: -`이고 top_paths 아래 줄은 없다.

JSON 형식(`--json`): 공백 없는 한 줄 + `\n`, ASCII가 아닌 글자는 이스케이프하지 않는다. 키 순서는 다음과 같다.

```
{"records":..,"skipped":..,"first":..,"last":..,"bytes":..,"status":{"2xx":..,"3xx":..,"4xx":..,"5xx":..},
 "methods":{..},"latency_ms":{"p50":..,"p95":..,"p99":..},"peak_minute":{"minute":..,"count":..},
 "top_paths":[{"path":..,"count":..,"error_rate":"..%","p50":..,"p95":..}]}
```

레코드가 0개면 first, last, latency_ms, peak_minute는 `null`, methods는 `{}`이다.
