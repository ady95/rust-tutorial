# Claude Code 1회차 최종 보고 (원문)

`rust_app/`에 Rust 버전을 만들었고 `cargo build --release`는 경고 없이 성공합니다. 다만 이 환경에서는 빌드한 `wordfreq.exe`를 직접 실행하지 못했고, Python 기준 구현과 나란히 돌린 비교(`automation/compare.py`)도 아직 하지 않았습니다.

## 검증 결과

- **release 빌드 성공**, clippy 경고도 없습니다.
- **단위 테스트 26개 통과**: `cases.json`의 17개 케이스를 모두 프로세스 안에서 돌려, stdout·stderr·종료 코드를 바이트 단위로 비교합니다. 기대값은 Python 테스트에 있는 값을 쓰거나 픽스처를 보고 손으로 계산했습니다.
- **`rust_app/tests/cli.rs`의 13개 테스트는 실패**합니다. 코드 문제가 아니라 Windows 애플리케이션 제어 정책(os error 4551)이 빌드된 exe 실행을 막아서입니다. 같은 이유로 Python도 실행할 수 없었습니다.
- **직접 확인해 주셔야 할 것**: 아래 비교 스크립트입니다. 정책이 허용되는 환경에서 실행하면 최종 판정이 납니다.
  ```
  uv run python automation/compare.py
  ```
- `python_src/`, `tests/`, `contracts/`는 읽기만 했습니다. 파일은 `rust_app/` 안에만 만들었고, `git status`로 재확인하는 것은 권한이 없어 하지 못했습니다.

## 만든 파일

| 파일 | 내용 |
|---|---|
| `rust_app/Cargo.toml` | 실행 파일 이름 `wordfreq`, 외부 의존성 없음 |
| `rust_app/.gitignore` | `/target` 제외 |
| `rust_app/src/main.rs` | 파일 읽기, 오류 메시지, 종료 코드(0/1/2), 프로세스 안 테스트 |
| `rust_app/src/cli.rs` | Python argparse(3.12)의 인자 해석 방식을 옮긴 부분 |
| `rust_app/src/report.rs` | 단어 자르기, 빈도 세기, 텍스트·JSON 출력 |
| `rust_app/src/pystr.rs` | Python 문자열 규칙 맞추기: 공백 판정, 소문자 변환, `int()` 파싱 |
| `rust_app/tests/cli.rs` | 실행 파일을 띄워 확인하는 테스트 (이 환경에서는 실패) |

계약에는 없지만 종료 코드에 영향을 주는 Python 동작도 맞췄습니다.
- **인자 해석**: `--to 5` 같은 축약, `--top=5`, `-hh`, `--` 구분자, `-5`를 파일 이름으로 보는 동작.
- **`--top` 값**: `" 7 "`, `1_0`, `３` 같은 값도 Python `int()`처럼 받습니다.
- **경로**: `""`는 `.`으로, `a.txt/`는 `a.txt`로 엽니다(pathlib과 같음).
- **"파일 없음" 판정**: Windows 오류 코드를 Python과 같은 기준으로 분류합니다.

## Python과 다르게 동작할 수 있는 부분

1. **Unicode 버전**: Python 3.12는 Unicode 15.0을 쓰고 Rust 표준 라이브러리는 더 새 버전을 씁니다. 아는 차이(Garay 문자 등 새로 생긴 대문자, 십진 숫자 표)는 코드에 직접 넣었습니다. 이 목록은 기억에 의존해 만들었고 Python과 대조하지 못했습니다. 그 밖에 cased 속성이 바뀐 글자가 Σ 옆에 오면 끝 시그마(ς) 처리가 다를 수 있습니다.
2. **인자 오류의 stderr 문구**: 계약상 비교 대상은 아니며, argparse 문구를 대략 흉내만 냈습니다.
3. **도움말(`-h`)**: 문구는 기본 터미널 너비 기준으로 고정했습니다. `COLUMNS`가 아주 작으면 Python은 줄을 바꾸지만 Rust는 그대로 출력합니다.
4. **3.12 패치 버전 차이**: `--`가 FILE 바로 옆에 붙지 않은 경우(예: `x --json --`)나 `-5x`처럼 음수 비슷한 인자의 처리는 3.12.x 패치마다 argparse 세부가 달라 결과가 다를 수 있습니다.
5. **UTF-8로 표현할 수 없는 인자**: 이런 FILE 인자(Windows의 짝 없는 서로게이트 등)는 Python이 오류 메시지를 출력하다 traceback과 함께 종료 코드 1로 죽습니다. Rust는 깨진 글자를 U+FFFD로 바꿔 메시지를 출력합니다. 종료 코드는 둘 다 1입니다.
6. **stdout 쓰기 실패**: 파이프가 닫힌 경우 Rust는 120으로 끝납니다. 출력이 작을 때의 Python 동작에 맞춘 것이고, 출력이 8KB를 넘으면 Python은 1로 끝납니다.
7. **긴 경로와 환경 변수**:
   - 260자를 넘는 Windows 경로는 Rust가 열 수 있지만, LongPaths 설정이 꺼진 Python은 실패할 수 있습니다.
   - 환경 변수 `PYTHONINTMAXSTRDIGITS`(정수 자릿수 상한 기본 4300)는 반영하지 않았습니다.
8. **Windows 명령행 분해**: 따옴표 안의 `""` 같은 경우 CRT와 Rust의 규칙이 미세하게 다를 수 있습니다.
