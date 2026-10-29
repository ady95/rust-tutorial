# 이식 보고서: wordfreq (split1)

이 보고서의 수치는 파이프라인 기록(sessions.jsonl, gate_*.json, audit.jsonl, heldout.json)에서 계산했다.
에이전트가 쓴 글은 마지막 절에 따로 붙였다.

## 결과

| 항목 | 값 |
|---|---|
| 모드 | split (계획 사용: True) |
| 종료 이유 | gate_passed |
| 라운드 | 1 / 최대 4 |
| 확인 게이트(다른 무작위 입력) | True |
| 추정 비용 | $8.3152 (상한 $10.0) |
| 실행 파일 | `artifacts/wordfreq` sha256 `0162ad18290015be…` |
| Rust 코드 | 5개 파일 1835줄 |

숨긴 평가: 6/6 일치

| 입력 | 결과 | 다른 코드 포인트 수 |
|---|---|---|
| shape A{c}B | 같음 | 0 |
| shape {c}Σ | 같음 | 0 |
| shape Σ{c} | 같음 | 0 |
| shape A{c}Σ | 같음 | 0 |
| u0295_sigma.txt | 같음 | - |
| new_letters.txt | 같음 | - |

계획의 위험 점검 입력: 20/20 일치

## 미검증 항목과 사람이 정할 일

에이전트 노트의 '확신하지 못하는 부분'을 그대로 옮겼다. 게이트와 숨긴 평가는 이 항목을 시험하지 않는다.

- R12: UTF-8 이 아닌 옵션 값·옵션·남는 인자에서 기준 구현은 1(UnicodeEncodeError), 계약은 2. Rust 는 계약대로 2.
- 예외 표는 Rust Unicode 17.0.0 기준. 툴체인이 바뀌면 전수 비교 테스트가 실패한다. rustc/cargo 버전 명령은 거부되어 보지 못했다.
- 도움말 쓰기 실패 시 종료 코드, 빈 경로 '' 처리, Windows 경로는 계약 밖이거나 실행하지 않았다.
- `uv run pytest` 는 허용 목록에 없어 실행하지 못했다.

## 라운드별 기록

| 라운드 | 결과 | 턴 | 시간(초) | 비용 | 코드 변경 | 게이트 실패 단계 | fuzz seed |
|---|---|---|---|---|---|---|---|
| 1 | success | 9 | 3650.7 | $8.3152 | True | 없음 | 65321752 |

## 도구 호출과 권한

도구 호출(메인 에이전트): Bash 64, Read 33, Write 27, Edit 15, Grep 8, Glob 4, Agent 4

서브에이전트 호출: implementer 2, verifier 2

| 역할 | 허용 | 거부 |
|---|---|---|
| coordinator | 8 | 0 |
| implementer_v2 | 85 | 7 |
| verifier | 49 | 5 |

거부된 호출(처음 10건):

- implementer_v2 Bash `/home/dev/work/ch08_ws/split1/.venv/bin/python -c "import sy` — 명령을 잇거나(; && ||) 파일로 쓰는(> <) 구문, 명령 치환은 허용하지 않습니다. 한 번에 명령 하나만 실행하세요
- implementer_v2 Bash `rustc --version` — implementer_v2: 허용 목록에 없는 명령입니다: rustc --version
- implementer_v2 Bash `cargo --version` — implementer_v2: 허용 목록에 없는 명령입니다: cargo --version
- implementer_v2 Bash `python3 /home/dev/work/ch08_ws/split1/verify/env_info.py` — implementer_v2: 허용 목록에 없는 명령입니다: python3 /home/dev/work/ch08_ws/split1/verify/env_info.py
- implementer_v2 Glob `**/library/core/src/unicode/unicode_data.rs` — implementer_v2: 작업 폴더 밖(/home/dev/.rustup)은 읽을 수 없습니다
- implementer_v2 Bash `uv run pytest -q` — implementer_v2: 허용 목록에 없는 명령입니다: uv run pytest -q
- verifier Bash `python3 -c "import os,sys;print(sys.version, os.getuid(), os` — 명령을 잇거나(; && ||) 파일로 쓰는(> <) 구문, 명령 치환은 허용하지 않습니다. 한 번에 명령 하나만 실행하세요
- verifier Bash `python3 /home/dev/work/ch08_ws/split1/verify/x_env.py` — verifier: 허용 목록에 없는 명령입니다: python3 /home/dev/work/ch08_ws/split1/verify/x_env.py
- verifier Read `/tmp/claude-1000/-home-dev-work-ch08-ws-split1/ff533577-f443` — verifier: 작업 폴더 밖(/tmp/claude-1000/-home-dev-work-ch08-ws-split1/ff533577-f443-4372-a63f-d46aa0ba16d3/tasks/ba9mfxo7n.output)은 읽을 수 없습니다
- verifier Read `/tmp/claude-1000/-home-dev-work-ch08-ws-split1/ff533577-f443` — verifier: 작업 폴더 밖(/tmp/claude-1000/-home-dev-work-ch08-ws-split1/ff533577-f443-4372-a63f-d46aa0ba16d3/tasks/btcgmr2h6.output)은 읽을 수 없습니다

## 환경

| 항목 | 값 |
|---|---|
| claude_code | 2.1.299 |
| model | claude-opus-5-5 |
| rustc | rustc 1.99.1 (58cf8f9c3 2026-10-13) |
| cargo | cargo 1.99.1 (5f94df478 2026-08-27) |
| python | Python 3.12.3 |
| os | Linux 6.18.33.2-microsoft-standard-WSL2 |
| claude_agent_sdk | 0.2.174 |
| sha256(baseline.lock) | `fd86a51b2772bc53…` |
| sha256(port/plan.json) | `4a4ff894303eafd7…` |

## 에이전트의 마지막 응답 (검증하지 않은 서술)

이식을 마쳤습니다. 계약을 어긴 차이는 하나 나왔고 고친 뒤 재검증까지 통과했습니다. 남은 차이 둘은 계약이 정하지 않은 부분이라 결정이 필요합니다. verifier가 더 찾지 못해서 여기서 멈췄습니다. 예산은 약 $1.7 남았습니다.

**구현 결과**
- `python_src/wordfreq.py`를 외부 크레이트 없이 표준 라이브러리만 쓰는 Rust 바이너리로 옮겼습니다(`rust_app/src/`의 `main.rs`, `cli.rs`, `text.rs`, `output.rs`).
- 사람이 만든 비교 도구는 모두 통과했습니다.
  - `compare.py`: 22/22
  - `scenarios.py`: 15/15
  - `fuzz.py`: 3회 모두 통과
  - `cargo test`: 실패 없음
- 소문자 변환은 Unicode 버전 차이(Python 15.0, Rust 17.0) 때문에 결과가 갈립니다. Python 결과와 모든 코드 포인트를 비교해 Rust에만 있는 변환 55글자를 찾았고, 이 결과만으로 예외 목록을 만들었습니다. Final_Sigma 판단에 쓰는 글자 분류가 다른 196글자도 같은 방식으로 맞췄습니다.

**검증과 수정**
- verifier가 위험 R1~R12를 모두 공략했습니다. 모든 코드 포인트, `--top` 값 4만여 가지, 인자 조합 8만여 가지, 경로·읽기 오류 등을 시험했고 차이는 3건이었습니다.
- **D1(계약 5절 위반, 수정함):** `-h`/`--help` 도움말을 쓰다 stdout 쓰기에 실패하면 Rust는 0으로 끝났습니다. Python 기준 구현은 120입니다.
  - Rust도 120으로 끝나게 바꿨습니다. 계약은 0이 아니기만 하면 되어서, 기준 구현과 같은 값을 골랐습니다.
  - 재검증에서 닫힌 파이프와 `/dev/full` 두 경우 모두 Python과 종료 코드가 같았습니다.
  - stderr 내용은 다릅니다. Python은 종료할 때 예외 메시지를 남기고 Rust는 아무것도 쓰지 않습니다. 계약상 출력 실패 때의 stderr는 비교 대상이 아니라서 그대로 두었습니다.

**결정이 필요한 것**
1. **D2 — 좁은 터미널에서 도움말이 다름:** `COLUMNS`가 48보다 작으면 Python은 도움말 줄을 바꾸고, Rust는 고정 문자열을 씁니다. 계약에 도움말 규정이 없어 맞출지 정해야 합니다(plan.json 열린 질문 3).
2. **D3 — 표준 출력·오류 fd가 닫힌 채 실행:** Python은 예외로 죽어 1로 끝나고, Rust는 정상 실행해 0(인자 오류면 2)으로 끝납니다. 기준 구현이 비정상 종료하는 경우라 Rust를 맞추지 않았습니다. 계약에 넣을지 정해야 합니다.
3. **R12 — 계약을 따라 일부러 다르게 함:** UTF-8이 아닌 `--top` 값이나 옵션에서 Python은 1로 끝나는데, Rust는 계약 4절대로 2로 끝납니다.

**확인하지 못한 것**
- `uv run pytest`가 허용 목록에 없어 거부됐습니다. 우회하지 않았고, `tests/test_wordfreq.py`는 실행하지 못했습니다.
- verifier가 `verify/findings.md`를 쓰지 못해 결과는 응답과 `verify/x_*.log`에만 남아 있습니다.
- 다음은 시험하지 않았습니다: FIFO·소켓·`/proc` 같은 특수 파일, 다른 로캘, Windows, 32비트 환경.
- `verify/x_work_fs/locked`는 권한이 0인 디렉터리라 지울 때 주의가 필요합니다.

보고서는 `reports/implementation.md`와 `reports/port_notes.md`에 있습니다.

## 에이전트가 쓴 노트 (검증하지 않은 서술)

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
