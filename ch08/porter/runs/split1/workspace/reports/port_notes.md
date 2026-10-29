# port notes (wordfreq → Rust)

자세한 내용은 reports/implementation.md 에 있다.

## (1) 특별히 처리한 Python 동작
- argparse 3.12.3 동작을 표준 라이브러리 소스대로 옮긴 바이트 기반 파서: `--`, `-`, `--top=N`, 접두어 약어, 모호한 약어, 반복 시 마지막 값, 음수 모양 위치 인자(Unicode Nd `\d`, 끝의 `\n` 허용), 공백 든 `-` 인자, `-h` 묶음, 도움말(같은 바이트, 0).
- positive_int: ASCII 숫자만, 앞의 0 무시, 18자리 초과는 최대값.
- str.split() 공백 집합(U+001C–001F 포함) 하드코딩.
- str.lower(): Python 3.12(Unicode 15.0)와 Rust(Unicode 17.0)의 전 코드 포인트 비교로 확정한 예외 표(소문자 55글자, Final_Sigma 분류 196글자)와 CPython handle_capital_sigma 와 같은 판단.
- pathlib 정규화(끝 `/`, `.` 성분, 빈 경로 → `.`), fs::read + from_utf8, NotFound 만 file not found.
- json.dumps(ensure_ascii=False) 이스케이프 직접 구현, 키 순서 고정.
- 출력은 write_all+flush 결과 확인, 실패 시 1. 매크로 출력·panic 경로 없음.

## (2) 직접 실행해 확인한 것
- cargo fmt --check, clippy -D warnings, build --release, test(단위 18 + 통합 8 통과).
- compare.py 22/22, scenarios.py 15/15, fuzz.py 3000×3회(seed 20261029, 7, 없음) 통과.
- verify/probe_cli.py 79/79, verify/all_codepoints.py 32/32(전 코드 포인트 × 5 문맥, 실제 실행 파일).

## (3) 확신하지 못하는 부분
- R12: UTF-8 이 아닌 옵션 값·옵션·남는 인자에서 기준 구현은 1(UnicodeEncodeError), 계약은 2. Rust 는 계약대로 2.
- 예외 표는 Rust Unicode 17.0.0 기준. 툴체인이 바뀌면 전수 비교 테스트가 실패한다. rustc/cargo 버전 명령은 거부되어 보지 못했다.
- 도움말 쓰기 실패 시 종료 코드, 빈 경로 '' 처리, Windows 경로는 계약 밖이거나 실행하지 않았다.
- `uv run pytest` 는 허용 목록에 없어 실행하지 못했다.
