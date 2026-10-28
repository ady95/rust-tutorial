# rust-tutorial

위키독스 책 「AI 에이전트로 Python을 Rust로 바꾸기 따라하기」의 예제 코드 저장소입니다.

- 책: https://wikidocs.net/book/21893

## 구성

| 폴더 | 장 | 내용 |
|---|---|---|
| `ch02/hello_python` | 02-1 | uv 프로젝트, pytest 첫 테스트 |
| `ch02/hello_rust` | 02-2 | Cargo 첫 프로젝트 |
| `ch03/` | 03장 | Python·Rust 동작 차이, 타입 힌트 비교, 테스트 강도 실험 |
| `tools/baseline.py` | 03-4 | 승인한 기준 구현(Python·테스트·계약)을 해시로 고정하고 검사 |
| `ch04/wordfreq` | 04장 | 단어 빈도 CLI — Python 기준 구현과 Claude Code가 만든 Rust 구현 |

실습 프로젝트는 같은 폴더 구조를 따릅니다.

```text
<project>/
├── python_src/     # Python 기준 구현 (에이전트가 수정하지 않음)
├── tests/          # pytest 테스트, fixtures(입력 데이터), cases.json(비교 케이스)
├── contracts/      # 동작 계약 (behavior_spec.md)
├── rust_app/       # 에이전트가 만든 Rust 프로젝트
├── automation/     # 비교·검증 스크립트
└── reports/        # 비교 결과, 실행 기록
```

## 실행 환경

- Python 3.12 (uv가 `.python-version`에 맞춰 설치), uv 0.13 이상
- Rust stable (rustup), Windows는 Visual Studio Build Tools(C++ 워크로드) 필요
- Claude Code

```bash
cd ch04/wordfreq
uv run pytest                                   # Python 기준 구현 테스트
cd rust_app && cargo build --release && cd ..   # Rust 빌드
uv run python automation/compare.py             # 두 구현 비교
uv run --no-project python ../../tools/baseline.py check   # 기준 구현이 그대로인지
```

## 주의

`rust_app/`의 Rust 코드는 책을 쓸 때 Claude Code가 생성하고 검증을 통과한 버전입니다. AI의 출력은 실행할 때마다 달라질 수 있으므로, 여러분이 직접 생성한 코드는 이 저장소와 다를 수 있습니다. 같은 검증(`compare.py`)을 통과하면 정상입니다.

`tests/fixtures/`의 파일은 줄바꿈까지 바이트 단위로 의미가 있습니다. `.gitattributes`가 Windows 체크아웃 시 줄바꿈 변환을 막습니다.
