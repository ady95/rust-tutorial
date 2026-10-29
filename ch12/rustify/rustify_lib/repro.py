"""재현성과 산출물 검사 (12-4).

- env_info: 실행 환경의 버전을 기록한다(에이전트 출력은 재현되지 않지만, 검증은 같은 환경에서 다시 할 수 있어야 한다)
- scan_outputs: 기록 폴더로 옮기는 산출물에 비밀처럼 보이는 문자열이 있는지 본다
- replay: 기록된 Rust 소스만으로 깨끗한 폴더에서 다시 빌드하고, 기록된 시드로 게이트를 다시 실행한다
"""

from __future__ import annotations

import hashlib
import platform
import re
import shutil
import subprocess
from importlib import metadata
from pathlib import Path

SECRET_PATTERNS = {
    "Anthropic API 키": re.compile(rb"sk-ant-[A-Za-z0-9_-]{20,}"),
    "OpenAI API 키": re.compile(rb"sk-(proj-)?[A-Za-z0-9]{32,}"),
    "GitHub 토큰": re.compile(rb"gh[pousr]_[A-Za-z0-9]{30,}"),
    "AWS 키": re.compile(rb"AKIA[0-9A-Z]{16}"),
    "개인 키": re.compile(rb"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    "홈 경로": re.compile(re.escape(str(Path.home()).encode()) + rb"/"),
}


def _version(cmd: list[str]) -> str | None:
    try:
        out = subprocess.run(cmd, capture_output=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        return None
    text = (out.stdout or out.stderr).decode("utf-8", "replace").strip().splitlines()
    return text[0] if out.returncode == 0 and text else None


def cpu_model() -> str:
    try:
        for line in Path("/proc/cpuinfo").read_text().splitlines():
            if line.startswith("model name"):
                return line.split(":", 1)[1].strip()
    except OSError:
        pass
    return platform.processor()


def env_info(workspace: Path | None = None) -> dict:
    home = Path.home()
    python = workspace / ".venv" / "bin" / "python" if workspace else None
    os_name = None
    if Path("/etc/os-release").exists():
        for line in Path("/etc/os-release").read_text().splitlines():
            if line.startswith("PRETTY_NAME="):
                os_name = line.split("=", 1)[1].strip('"')
    try:
        sdk = metadata.version("claude-agent-sdk")
    except metadata.PackageNotFoundError:
        sdk = None
    return {
        "os": os_name, "kernel": platform.release(), "cpu": cpu_model(),
        "claude_code": _version([str(home / ".local" / "bin" / "claude"), "--version"]),
        "claude_agent_sdk": sdk,
        "codex": _version([shutil.which("codex") or "codex", "--version"]),
        "rustc": _version(["rustc", "-V"]), "cargo": _version(["cargo", "-V"]),
        "python": _version([str(python), "-V"]) if python and python.exists() else None,
        "uv": _version(["uv", "--version"]), "hyperfine": _version(["hyperfine", "--version"]),
    }


def scan_outputs(root: Path) -> list[dict]:
    found = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.stat().st_size > 5_000_000:
            continue
        data = path.read_bytes()
        for label, pattern in SECRET_PATTERNS.items():
            if pattern.search(data):
                found.append({"file": path.relative_to(root).as_posix(), "kind": label})
    return found


def sha256(path: Path) -> str | None:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
