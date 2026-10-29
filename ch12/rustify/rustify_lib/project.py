"""입력 프로젝트 검사와 승인 (12-1).

사람이 만드는 것은 Python 뿐이다: 기준 구현(python_src/), 테스트(tests/: pytest, 비교 케이스, 입력 생성 규칙),
계약(contracts/behavior_spec.md), 실행 정보(automation/port.json). 이 모듈은 그 입력이 자동 이식을 시작해도 될
상태인지 실행해서 확인한다. 하나라도 '불가'면 에이전트를 부르지 않는다(비용 0).
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

HARNESS = Path(__file__).resolve().parent / "harness"
REQUIRED = ["python_src", "tests", "contracts/behavior_spec.md", "automation/port.json", "pyproject.toml", "uv.lock"]


@dataclass
class Item:
    name: str
    status: str  # OK | 주의 | 불가
    detail: str = ""


@dataclass
class CheckReport:
    project: str
    items: list[Item] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return all(i.status != "불가" for i in self.items)

    def add(self, name: str, status: str, detail: str = "") -> None:
        self.items.append(Item(name, status, detail))

    def render(self) -> str:
        width = max(len(i.name) for i in self.items)
        lines = [f"{i.status:<3} {i.name:<{width}}  {i.detail}".rstrip() for i in self.items]
        verdict = "시작 가능" if self.ok else "시작 불가"
        return "\n".join(lines) + f"\n\n{self.project}: {verdict}"


def run(cmd: list[str], cwd: Path, stdin: bytes = b"", timeout: int = 600) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=cwd, input=stdin, capture_output=True, timeout=timeout)


def load_manifest(project: Path) -> dict:
    return json.loads((project / "automation" / "port.json").read_text(encoding="utf-8"))


def check_project(project: Path, require_lock: bool = True) -> CheckReport:
    report = CheckReport(project.name)
    missing = [name for name in REQUIRED if not (project / name).exists()]
    report.add("구성", "불가" if missing else "OK", f"없음: {', '.join(missing)}" if missing else "필수 파일 6가지")
    if missing:
        return report

    # port.json: 실행 파일 이름, 기준 구현 경로, 게이트 검사
    try:
        manifest = load_manifest(project)
        problems = []
        if not re.fullmatch(r"[A-Za-z0-9_-]+", manifest.get("binary", "")):
            problems.append("binary 이름")
        if not (project / manifest.get("python", "?")).is_file():
            problems.append("python 경로")
        for check in manifest.get("checks", []):
            if check.get("builtin") == "compare" and not (project / "tests" / "cases.json").is_file():
                problems.append("compare 에 tests/cases.json 필요")
            if check.get("builtin") == "fuzz" and not (project / "tests" / "strategies.py").is_file():
                problems.append("fuzz 에 tests/strategies.py 필요")
            if "builtin" not in check and "cmd" not in check:
                problems.append(f"{check.get('name')}: builtin 이나 cmd 필요")
        if not manifest.get("checks"):
            problems.append("checks 가 비어 있음")
        report.add("port.json", "불가" if problems else "OK",
                   ", ".join(problems) or f"검사 {', '.join(c['name'] for c in manifest['checks'])}"
                   + (", 성능 측정 있음" if manifest.get("bench") else ""))
    except (json.JSONDecodeError, KeyError) as err:
        report.add("port.json", "불가", f"읽을 수 없음: {err}")
        return report

    # 기준 고정: 사람이 승인한 그대로인가
    if require_lock:
        lock = run([sys.executable, str(HARNESS / "baseline.py"), "check"], project)
        detail = (lock.stdout or lock.stderr).decode("utf-8", "replace").strip().splitlines()
        report.add("승인(baseline.lock)", "OK" if lock.returncode == 0 else "불가", "; ".join(detail[:3]))

    # 테스트: 기준 구현이 자기 테스트를 통과하는가
    sync = run(["uv", "sync", "-q"], project)
    if sync.returncode != 0:
        report.add("환경(uv sync)", "불가", sync.stderr.decode("utf-8", "replace").strip()[-200:])
        return report
    tests = run(["uv", "run", "pytest", "-q", "-p", "no:cacheprovider"], project)
    summary = tests.stdout.decode("utf-8", "replace").strip().splitlines()[-1:] or ["?"]
    report.add("pytest", "OK" if tests.returncode == 0 else "불가", summary[0])

    # 비교 케이스: 기준 구현을 두 번 실행해 결과가 같은가(같지 않으면 바이트 비교를 할 수 없다)
    cases_path = project / "tests" / "cases.json"
    cases = json.loads(cases_path.read_text(encoding="utf-8")) if cases_path.is_file() else []
    if cases and not all("args" in case for case in cases):
        report.add("비교 케이스", "주의", f"{len(cases)}개, CLI 형식이 아님(프로젝트 전용 비교 도구가 판정, 결정성 확인 안 함)")
    elif cases:
        python = [str(project / ".venv" / "bin" / "python"), manifest["python"]]
        unstable, codes = [], {}
        for case in cases:
            data = bytes.fromhex(case["stdin_hex"]) if "stdin_hex" in case else case.get("stdin", "").encode()
            first, second = (run(python + case["args"], project, data, timeout=60) for _ in range(2))
            if (first.returncode, first.stdout, first.stderr) != (second.returncode, second.stdout, second.stderr):
                unstable.append(case["name"])
            codes[first.returncode] = codes.get(first.returncode, 0) + 1
        spread = ", ".join(f"종료 {k}: {v}" for k, v in sorted(codes.items()))
        report.add("비교 케이스", "불가" if unstable else ("OK" if len(codes) > 1 else "주의"),
                   f"{len(cases)}개({spread})" + (f", 실행마다 다름: {', '.join(unstable)}" if unstable else "")
                   + ("" if len(codes) > 1 else ", 오류 경로 케이스가 없음"))

    # 입력 생성 규칙: fuzz 하네스가 불러 쓸 수 있는가
    if (project / "tests" / "strategies.py").is_file():
        probe = run(["uv", "run", "python", "-c",
                     "import sys; sys.path.insert(0, 'tests'); import strategies; "
                     "print(strategies.cases().example())"], project)
        report.add("입력 생성 규칙", "OK" if probe.returncode == 0 else "불가",
                   "tests/strategies.py 의 cases()" if probe.returncode == 0
                   else probe.stderr.decode("utf-8", "replace").strip().splitlines()[-1][:200])

    # 계약: 비교하지 않는 항목과 범위 밖을 적었는가(없으면 판정할 기준이 없는 차이가 생긴다)
    contract = (project / "contracts" / "behavior_spec.md").read_text(encoding="utf-8")
    hints = [word for word in ("비교 안 함", "범위 밖", "종료 코드") if word not in contract]
    report.add("계약", "주의" if hints else "OK",
               f"{len(contract)}자" + (f", 없는 표현: {', '.join(hints)}" if hints else ""))
    return report


def approve(project: Path) -> int:
    """사람이 내용을 검토한 뒤 실행한다. 검사(승인 제외)를 통과하면 baseline.lock 을 새로 쓴다."""
    report = check_project(project, require_lock=False)
    print(report.render())
    if not report.ok:
        print("검사를 통과하지 못해 승인하지 않았습니다", file=sys.stderr)
        return 1
    lock = run([sys.executable, str(HARNESS / "baseline.py"), "lock"], project)
    print(lock.stdout.decode("utf-8", "replace").strip())
    return lock.returncode
