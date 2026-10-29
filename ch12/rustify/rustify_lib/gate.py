"""검증 게이트 (8장 porter_lib/gate.py 를 정리한 것, 12-2·12-4).

순서: 기준 고정 검사 → 하네스 검사 → fmt → clippy → test → 릴리스 빌드 → 프로젝트 검사(port.json 의 checks).
에이전트의 보고가 아니라 이 게이트의 결과로 완료를 판정한다.

게이트는 에이전트가 쓴 코드(build.rs, 테스트, 실행 파일)를 실행한다. 그래서
- 비밀로 보이는 환경 변수를 지우고
- bubblewrap 이 있으면 네트워크를 끊고 인증 정보 폴더를 가린 채 실행한다(12-4)
"""

from __future__ import annotations

import hashlib
import json
import os
import random
import re
import shutil
import subprocess
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

FEEDBACK_LINES = 40
FEEDBACK_LINE_BYTES = 300
SECRET_ENV = re.compile(r"(KEY|TOKEN|SECRET|PASSWORD|CREDENTIAL)", re.IGNORECASE)
HIDDEN_DIRS = [".ssh", ".claude", ".codex", ".config/gh", ".aws", ".docker"]

BUILTIN = {
    "compare": ["uv", "run", "python", ".rustify/compare_cli.py", "--rust", "{bin}"],
    "fuzz": ["uv", "run", "python", ".rustify/fuzz_cli.py", "--rust", "{bin}", "--seed", "{seed}"],
}


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
    sandboxed: bool = False

    def failing(self) -> list[str]:
        return [s.name for s in self.steps if not s.ok]


def clean_env(workspace: Path) -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if not SECRET_ENV.search(k)}
    if (workspace / ".cargo-home").is_dir():  # Codex 엔진은 크레이트 캐시를 작업 폴더 안에 둔다(engines.py)
        env["CARGO_HOME"] = str(workspace / ".cargo-home")
    env.pop("VIRTUAL_ENV", None)
    env["UV_OFFLINE"] = "1"  # 프로젝트 환경은 준비 단계에서 만들어 둔다. 게이트는 네트워크 없이 돈다
    home = Path.home()
    env["PATH"] = f"{home / '.cargo' / 'bin'}:{home / '.local' / 'bin'}:{env.get('PATH', '')}"
    return env


def sandbox_prefix(workspace: Path) -> list[str]:
    """bubblewrap: 파일 시스템은 읽기 전용으로 보이고, 작업 폴더·캐시만 쓸 수 있고, 네트워크는 없다."""
    if not shutil.which("bwrap"):
        return []
    home = Path.home()
    args = ["bwrap", "--ro-bind", "/", "/", "--dev", "/dev", "--proc", "/proc", "--tmpfs", "/tmp",
            "--unshare-net", "--die-with-parent", "--bind", str(workspace), str(workspace)]
    for writable in (home / ".cache" / "uv", home / ".cargo" / "registry"):
        if writable.exists():
            args += ["--bind", str(writable), str(writable)]
    for hidden in HIDDEN_DIRS:
        if (home / hidden).exists():
            args += ["--tmpfs", str(home / hidden)]
    return args


def run_step(name: str, cmd: list[str], cwd: Path, prefix: list[str], timeout: int = 900) -> Step:
    started = time.monotonic()
    try:
        proc = subprocess.run(prefix + cmd, cwd=cwd, capture_output=True, timeout=timeout, env=clean_env(cwd))
        code, output = proc.returncode, proc.stdout + proc.stderr
    except subprocess.TimeoutExpired as err:
        code, output = -1, (err.stdout or b"") + (err.stderr or b"") + b"\n[rustify] timeout"
    except OSError as err:
        code, output = -1, f"[rustify] cannot run: {err}".encode()
    lines = output.decode("utf-8", "replace").splitlines()
    return Step(name, code == 0, code, round(time.monotonic() - started, 2),
                [line[:FEEDBACK_LINE_BYTES] for line in lines[-FEEDBACK_LINES:]])


def harness_digest(workspace: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted((workspace / ".rustify").rglob("*")):
        if path.is_file() and "__pycache__" not in path.parts:
            digest.update(path.relative_to(workspace).as_posix().encode() + b"\0" + path.read_bytes())
    return digest.hexdigest()


def check_command(check: dict) -> list[str]:
    if "builtin" in check:
        cmd = list(BUILTIN[check["builtin"]])
        if "examples" in check:
            cmd += ["--examples", str(check["examples"])]
        return cmd
    return list(check["cmd"])


def run_gate(workspace: Path, manifest: dict, harness_sha: str, seed: int | None = None,
             sandbox: bool = True, offline: bool = False) -> GateResult:
    seed = seed if seed is not None else random.randrange(1, 2**31)
    prefix = sandbox_prefix(workspace) if sandbox else []
    toml = ["--manifest-path", "rust_app/Cargo.toml"]
    cargo_flags = ["--offline"] if offline else []
    binary = f"rust_app/target/release/{manifest['binary']}"
    steps = [run_step("baseline", ["python3", ".rustify/baseline.py", "check"], workspace, prefix)]
    harness_ok = harness_digest(workspace) == harness_sha
    steps.append(Step("harness", harness_ok, 0 if harness_ok else 1, 0.0,
                      [] if harness_ok else [".rustify/ 의 비교 도구가 바뀌었습니다"]))
    if not (steps[0].ok and harness_ok):
        return GateResult(False, seed, steps, protected_changed=True, sandboxed=bool(prefix))
    if not (workspace / "rust_app" / "Cargo.toml").exists():
        steps.append(Step("cargo-project", False, -1, 0.0, ["rust_app/Cargo.toml 이 없습니다"]))
        return GateResult(False, seed, steps, sandboxed=bool(prefix))
    steps.append(run_step("fmt", ["cargo", "fmt", *toml, "--", "--check"], workspace, prefix))
    steps.append(run_step("clippy", ["cargo", "clippy", *cargo_flags, *toml, "--all-targets", "--", "-D", "warnings"],
                          workspace, prefix))
    steps.append(run_step("test", ["cargo", "test", *cargo_flags, *toml, "--no-fail-fast"], workspace, prefix))
    build = run_step("build", ["cargo", "build", *cargo_flags, *toml, "--release"], workspace, prefix)
    steps.append(build)
    for check in manifest["checks"]:
        if not build.ok:
            steps.append(Step(check["name"], False, -1, 0.0, ["빌드 실패로 실행하지 않음"]))
            continue
        cmd = [part.format(bin=binary, seed=seed) for part in check_command(check)]
        steps.append(run_step(check["name"], cmd, workspace, prefix))
    return GateResult(all(s.ok for s in steps), seed, steps, sandboxed=bool(prefix))


def feedback(gate: GateResult) -> str:
    parts = [f"### {s.name} (exit {s.exit_code})\n```\n" + "\n".join(s.tail) + "\n```" for s in gate.steps if not s.ok]
    passed = ", ".join(s.name for s in gate.steps if s.ok) or "없음"
    return f"통과: {passed}\n실패: {', '.join(gate.failing())}\n\n" + "\n\n".join(parts)


def save(gate: GateResult, path: Path) -> None:
    path.write_text(json.dumps(asdict(gate), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
