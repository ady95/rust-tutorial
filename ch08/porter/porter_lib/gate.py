"""검증 게이트 (08-3). 에이전트의 보고가 아니라 이 게이트의 결과로 완료를 판정한다.

순서: 기준 고정 검사 → fmt → clippy → test → 릴리스 빌드 → 프로젝트 검사(automation/port.json 의 checks).
기준 고정 검사가 실패하면(에이전트가 사람의 파일을 바꿈) 나머지를 실행하지 않는다.
"""

from __future__ import annotations

import json
import os
import random
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

FEEDBACK_LINES = 40  # 단계마다 에이전트에게 돌려줄 출력 줄 수(뒤쪽)
FEEDBACK_LINE_BYTES = 300


@dataclass
class Step:
    name: str
    ok: bool
    exit_code: int
    seconds: float
    tail: list[str] = field(default_factory=list)


@dataclass
class GateResult:
    ok: bool
    fuzz_seed: int
    steps: list[Step]
    protected_changed: bool = False

    def failing(self) -> list[str]:
        return [s.name for s in self.steps if not s.ok]

    def to_dict(self) -> dict:
        return asdict(self)


def _env() -> dict[str, str]:
    env = dict(os.environ)
    env.pop("VIRTUAL_ENV", None)  # 파이프라인 자신의 가상 환경이 프로젝트의 uv 실행에 섞이지 않게
    home = Path.home()
    env["PATH"] = f"{home / '.cargo' / 'bin'}:{home / '.local' / 'bin'}:{env.get('PATH', '')}"
    return env


def run_step(name: str, cmd: list[str], cwd: Path, timeout: int = 900) -> Step:
    started = time.monotonic()
    try:
        proc = subprocess.run(cmd, cwd=cwd, capture_output=True, timeout=timeout, env=_env())
        code, output = proc.returncode, proc.stdout + proc.stderr
    except subprocess.TimeoutExpired as err:
        code, output = -1, (err.stdout or b"") + (err.stderr or b"") + b"\n[porter] timeout"
    except OSError as err:
        code, output = -1, f"[porter] cannot run: {err}".encode()
    lines = output.decode("utf-8", "replace").splitlines()
    tail = [line[:FEEDBACK_LINE_BYTES] for line in lines[-FEEDBACK_LINES:]]
    return Step(name, code == 0, code, round(time.monotonic() - started, 2), tail)


def run_gate(workspace: Path, manifest: dict, seed: int | None = None) -> GateResult:
    seed = seed if seed is not None else random.randrange(1, 2**31)
    cargo = ["cargo"]
    toml = ["--manifest-path", "rust_app/Cargo.toml"]
    binary = f"rust_app/target/release/{manifest['binary']}"
    steps: list[Step] = []
    baseline = run_step("baseline", [sys.executable, ".porter/baseline.py", "check"], workspace)
    steps.append(baseline)
    if not baseline.ok:
        return GateResult(False, seed, steps, protected_changed=True)
    if not (workspace / "rust_app" / "Cargo.toml").exists():
        steps.append(Step("cargo-project", False, -1, 0.0, ["rust_app/Cargo.toml 이 없습니다"]))
        return GateResult(False, seed, steps)
    steps.append(run_step("fmt", cargo + ["fmt", *toml, "--", "--check"], workspace))
    steps.append(run_step("clippy", cargo + ["clippy", *toml, "--all-targets", "--", "-D", "warnings"], workspace))
    steps.append(run_step("test", cargo + ["test", *toml, "--no-fail-fast"], workspace))
    build = run_step("build", cargo + ["build", *toml, "--release"], workspace)
    steps.append(build)
    if build.ok:
        for check in manifest["checks"]:
            cmd = [part.format(bin=binary, seed=seed) for part in check["cmd"]]
            steps.append(run_step(check["name"], cmd, workspace))
    else:
        steps.extend(Step(c["name"], False, -1, 0.0, ["빌드 실패로 실행하지 않음"]) for c in manifest["checks"])
    return GateResult(all(s.ok for s in steps), seed, steps)


def feedback(gate: GateResult) -> str:
    """실패한 단계의 마지막 출력만 모아 에이전트에게 줄 메시지를 만든다."""
    parts = []
    for step in gate.steps:
        if step.ok:
            continue
        parts.append(f"### {step.name} (exit {step.exit_code})\n```\n" + "\n".join(step.tail) + "\n```")
    passed = ", ".join(s.name for s in gate.steps if s.ok) or "없음"
    return f"통과: {passed}\n실패: {', '.join(gate.failing())}\n\n" + "\n\n".join(parts)


def save(gate: GateResult, path: Path) -> None:
    path.write_text(json.dumps(gate.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
