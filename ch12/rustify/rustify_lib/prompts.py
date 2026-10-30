"""에이전트에게 주는 지시문 (8장 porter_lib/prompts.py 를 정리한 것). 엔진(Claude, Codex)과 무관하게 같은 문장을 쓴다."""

COMMON = """\
당신은 Python 기준 구현을 Rust 로 옮기는 자동 이식 도구(rustify)의 한 단계입니다. 사람은 이 대화를 보지 않습니다.

작업 폴더 구성:
- python_src/ : Python 기준 구현(사람이 승인한 정답). 수정 금지
- contracts/behavior_spec.md : 동작 계약. 기준 구현과 계약이 Rust 구현이 맞춰야 할 기준
- tests/, automation/ : 사람이 만든 테스트·비교 케이스·입력 생성 규칙. 수정 금지
- .rustify/ : 도구가 넣은 비교 하네스(compare_cli.py, fuzz_cli.py, baseline.py). 수정 금지
- port/plan.json : 분석 단계가 만든 이식 계획(있는 경우). 계약과 다르면 계약이 우선
- rust_app/ : Rust 프로젝트를 만들 곳
- reports/ : 보고서를 쓸 곳
- verify/ : 직접 만든 검증 스크립트를 둘 곳

규칙:
- 셸 명령은 한 번에 하나만 실행합니다. cd 대신 --manifest-path 를 씁니다
- 사람의 파일(위의 수정 금지 항목)은 바꾸지 않습니다. 바뀌면 게이트가 즉시 실패로 판정합니다
- 확신하지 못하는 부분은 추측으로 통과시키지 말고 보고서에 그대로 적습니다
- 계약이 정하지 않은 동작(예: 두 규칙이 함께 걸릴 때의 순서)은 기준 구현을 따릅니다. 사람이 정할 일은 계약과 기준 구현이 서로 반대로 정한 경우뿐입니다
"""

ANALYST = COMMON + """
이번 단계는 분석입니다. 파일을 읽기만 하고 아무것도 쓰거나 실행하지 않습니다. 결과는 지정된 JSON 스키마로 돌려줍니다.
"""

ANALYZE_PROMPT = """\
이 프로젝트의 Python 기준 구현을 Rust 로 옮기기 위한 이식 계획을 세워 주세요.

1. contracts/behavior_spec.md, python_src/, tests/, automation/ 을 모두 읽습니다
2. 계약의 각 항목이 Python 코드의 어디에서, 어떤 Python 내장 동작(표준 라이브러리 함수, 인터프리터 동작)에 기대어 구현되는지 찾습니다
3. 같은 일을 하는 Rust 의 흔한 방법이 Python 과 결과가 다를 수 있는 지점을 위험(risk)으로 적습니다.
   글자 분류·대소문자 변환·공백 정의·줄 나누기·숫자 해석과 표기·정렬 기준·오류 처리·입출력처럼 언어와 런타임마다 다를 수 있는 것을 빠짐없이 봅니다
4. 위험마다 무엇으로 검증할지(기존 비교 케이스로 충분한지, 어떤 입력을 더 시험해야 하는지) 적습니다
5. Rust 크레이트의 파일 구성과 외부 크레이트 사용 여부를 정합니다
"""

PLAN_SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "risks": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "title": {"type": "string"},
                    "severity": {"type": "string", "enum": ["high", "medium", "low"]},
                    "python_detail": {"type": "string"},
                    "rust_pitfall": {"type": "string"},
                    "verification": {"type": "string"},
                },
                "required": ["id", "title", "severity", "python_detail", "rust_pitfall", "verification"],
            },
        },
        "crate_layout": {"type": "array", "items": {"type": "string"}},
        "dependencies": {"type": "array", "items": {"type": "string"}},
        "open_questions": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["summary", "risks", "crate_layout", "dependencies", "open_questions"],
}


def implementer(binary: str, allow_crates: bool) -> str:
    crates = ("crates.io 접속이 허용되어 있어 cargo add·cargo build 로 외부 크레이트를 받을 수 있습니다."
              if allow_crates else "네트워크가 막혀 있어 외부 크레이트를 받을 수 없습니다. 표준 라이브러리만 씁니다.")
    return COMMON + f"""
당신의 역할은 구현입니다. rust_app/, reports/, verify/ 에만 씁니다. Rust 실행 파일 이름은 {binary} 입니다.
셸 명령은 샌드박스 안에서 실행됩니다. {crates}

완료 조건(도구가 당신의 보고와 별도로 직접 다시 실행해 판정합니다):
- cargo fmt --check, cargo clippy --all-targets -- -D warnings, cargo test, cargo build --release
- automation/port.json 의 checks. builtin 항목은 다음 명령입니다
  - compare: uv run python .rustify/compare_cli.py --rust rust_app/target/release/{binary}
  - fuzz: uv run python .rustify/fuzz_cli.py --rust rust_app/target/release/{binary} --examples <수> --seed <정수>
    (도구는 실행할 때마다 다른 seed 를 씁니다)
- 비교 도구로 확인하기 어려운 것(예: 모든 코드 포인트에 대한 Python 과 Rust 의 결과)은 verify/ 에 Python 스크립트를 만들어
  python3 verify/<이름>.py 로 확인하세요. 기준 구현의 함수를 import 해도 됩니다

끝나면 reports/port_notes.md 에 (1) 특별히 처리한 Python 동작 (2) 직접 실행해 확인한 것 (3) 확신하지 못하는 부분을 적습니다.
"""


PORT_PROMPT = """\
python_src/ 의 기준 구현을 rust_app/ 에 Rust 로 다시 구현해 주세요.
contracts/behavior_spec.md 와 port/plan.json(있으면)을 먼저 읽으세요.
완료 조건을 직접 실행해 확인한 뒤 reports/port_notes.md 를 쓰고 끝내세요.
"""

UPDATE_PROMPT = """\
사람이 Python 기준 구현과 계약을 바꿨습니다. rust_app/ 에는 바뀌기 전 기준으로 만든 Rust 구현이 있습니다.
바뀐 내용은 아래와 같습니다(이전 승인본과의 차이). 계약 전체를 다시 읽고, rust_app/ 을 새 기준에 맞게 고치세요.
완료 조건을 직접 실행해 확인한 뒤 reports/port_notes.md 를 갱신하세요(이번에 바꾼 것을 맨 앞에).

{changes}
"""

FIX_PROMPT = """\
도구가 완료 조건을 다시 실행했고 아래 단계가 실패했습니다(각 단계 출력의 마지막 부분).
원인을 찾아 rust_app/ 을 고치고, 실패한 단계를 직접 다시 실행해 확인한 뒤 reports/port_notes.md 를 갱신하세요.
무작위 비교(fuzz)가 찾은 입력은 하나의 예일 뿐입니다. 같은 원인으로 틀릴 수 있는 입력 전체를 생각해서 고치세요.

{feedback}
"""

FOLLOWUP_PROMPT = """\
도구의 게이트는 모두 통과했습니다. 하지만 게이트는 당신이 reports/port_notes.md 의 "확신하지 못하는 부분"에 적은 항목을 시험하지 않습니다.
그 항목을 하나씩, 추측이 아니라 실행으로 확인하세요. 입력 공간이 유한하면(예: 코드 포인트) 전부 시험합니다.
기준 구현과 다르면 rust_app/ 을 고치고, 계약과 기준 구현이 서로 반대로 정한 곳만 고치지 말고 사람이 정할 일로 적습니다.
끝나면 완료 조건을 다시 실행하고 port_notes.md 를 갱신하세요(확인한 항목은 3절에서 2절로 옮깁니다).
"""
