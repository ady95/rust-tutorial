# stats 동작 계약 (behavior spec)

기준 구현: `python_src/stats.py` (3판, 승인일 2026-10-30)
다른 언어로 재구현할 때 아래 항목은 바이트 단위로 같아야 한다. "비교 안 함"으로 적힌 항목만 예외다.

## 1. 명령행

```
stats FILE
```

인자가 정확히 하나가 아니면 stderr에 `usage: stats FILE`을 쓰고 종료 코드 2.

## 2. 입력

1. 파일 전체를 UTF-8로 읽고 줄로 나눈다(Python `str.splitlines()`와 같은 규칙).
2. 각 줄의 앞뒤 공백을 떼고(`str.strip()`), 빈 줄은 건너뛴다.
3. 남은 줄은 Python `float()`가 받는 형식의 숫자여야 한다.

## 3. 정상 출력 (종료 코드 0, UTF-8, 줄바꿈 LF)

```
count: <개수>
sum: <합계>
mean: <평균>
mean2: <평균을 소수 둘째 자리로 반올림한 값>
stdev: <표본 표준편차>
min: <최솟값>
max: <최댓값>
```

| 필드 | 값의 정의 | 표기 |
|---|---|---|
| count | 숫자 개수 | 정수 |
| sum | Python `sum()`의 결과(오차 보정 합산) | Python `repr(float)` |
| mean | `statistics.mean()`의 결과(정확히 계산한 뒤 한 번만 반올림) | Python `repr(float)` |
| mean2 | `round(mean, 2)`(저장된 이진값 기준, 정확히 중간이면 짝수 쪽) | Python `repr(float)` |
| stdev | `statistics.stdev()`의 결과 | 고정 소수점 넷째 자리(`.4f`) |
| min, max | 최솟값, 최댓값 | Python `repr(float)` |

모든 필드는 바이트 단위로 같아야 한다(허용 오차 없음, 07-4).

## 4. 오류 (종료 코드 1, stdout은 비어 있어야 함)

| 상황 | stderr |
|---|---|
| 파일을 읽을 수 없음 | `stats: error: cannot read file: <FILE>` (정확히 일치) |
| 숫자가 아닌 줄 | `stats: error: not a number on line <N>: <줄>` (정확히 일치, N은 1부터, 빈 줄 포함) |
| 숫자가 2개 미만 | `stats: error: need at least 2 numbers` (정확히 일치) |
| inf·nan, 또는 너무 커서 inf가 되는 수 | 비교 안 함(종료 코드 1만 비교) |
| 파일이 UTF-8이 아님 | 비교 안 함(종료 코드 1만 비교). 기준 구현은 `stats: error: not valid UTF-8: <FILE>` |
| 표준편차가 실수 범위를 넘음(예: `1.7e308`과 `-1.7e308`) | 비교 안 함(종료 코드 1만 비교). 기준 구현은 `stats: error: result out of range` |

## 변경 기록

| 판 | 날짜 | 변경 |
|---|---|---|
| 1 | 2026-10-29 | 07-4 실험용(계약 문서 없이 지침으로만 전달) |
| 2 | 2026-10-29 | 계약 문서 작성. inf·nan 입력은 종료 코드 1, stderr 비교 안 함(1판 기준 구현은 Python 런타임 결함으로 비정상 종료) |
| 3 | 2026-10-30 | UTF-8이 아닌 파일과 표준편차 넘침을 종료 코드 1, stderr 비교 안 함으로 정하고 기준 구현이 직접 오류를 내게 고침(08-2에서 계약과 기준 구현의 불일치, 비정상 종료 확인) |
