# 계약 갱신(2026-10-30) 반영 내용

## 바꾼 것
- `rust_app/src/jsonout.rs`: 지수 표기의 양수 지수에 `+` 를 붙인다(`1e+16`, `1.5e+300`). 음수 지수는 그대로(`1e-7`). 단위 시험의 기대값도 갱신.
- `rust_app/src/http.rs`: HTTP/1.1 요청의 `Host` 헤더가 0개 또는 2개 이상이면 400. hyper 는 이를 스스로 검사하지 않아 처리기에서 직접 판정한다.

## 바꾸지 않은 것
- API 문서 경로(`/docs` 등)는 이전부터 404 였고 `docs-disabled` 케이스가 통과한다.
- 그 밖의 잘못된 HTTP 요청은 hyper 가 4xx 로 거부하거나 기준과 같은 코드를 내며, `malformed-http` 케이스가 통과한다.
- 동시성(5절)은 기존 구현(저장소 잠금 안에서 확인과 차감)이 그대로 통과한다.

## 직접 실행해 확인한 것
- `cargo fmt --check`, `cargo clippy --all-targets -- -D warnings`, `cargo test`(14 통과, 1 무시), `cargo build --release`: 통과
- compare: 23/23 일치(stats-exponent, docs-disabled, malformed-http 포함)
- fuzz: `--examples 400 --seed 20261030` 일치
- race: `--repeat 2 --requests 1000 --quantity 300` PASS 2/2

## 확신하지 못하는 부분
- fuzz 는 시드 하나만 실행했다. 다른 시드의 결과는 확인하지 못했다.
- 잘못된 HTTP 요청은 비교 케이스에 있는 것만 확인했다. 그 밖의 형태(예: HTTP/1.0 의 Host 처리)는 계약상 4xx 허용 범위로 보지만 기준 구현과 일일이 대조하지 않았다.
