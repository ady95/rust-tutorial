"""도구 호출 정책과 샌드박스 설정 (8장 porter_lib/policy.py 를 정리한 것, 12-4).

Claude 엔진에서만 쓴다. PreToolUse 훅 하나로 모든 도구 호출을 검사하고 감사 기록(audit.jsonl)을 남긴다.
셸 명령은 훅(무엇을 실행하나)과 샌드박스(실행된 것이 무엇을 할 수 있나) 두 겹으로 막는다.
"""

from __future__ import annotations

import json
import re
import shlex
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

PIPE_FILTERS = re.compile(r"^(head|tail|grep|wc|sort|uniq|cut|od|xxd)\b")
SHELL_CHAINING = re.compile(r";|&&|\|\||`|\$\(|>|<")

READ_ONLY = r"^(ls|cat|head|tail|wc|od|xxd|diff|cmp|grep|rg|find|file|stat)\b"
RUN_RUST = r"^(\./)?rust_app/target/(release|debug)/[\w-]+(\s|$)"
RUN_PYTHON = r"^(python3|uv run python) (python_src|verify)/[\w/.-]+\.py(\s|$)"
RUN_CHECKS = r"^(python3|uv run python) (automation|\.rustify)/[\w-]+\.py(\s|$)"

ROLES: dict[str, dict[str, list[str]]] = {
    "implementer": {
        "write": ["rust_app/", "reports/", "verify/"],
        "bash": [
            r"^cargo (new|init|build|check|test|run|clippy|fmt|add|tree|metadata)(\s|$)",
            RUN_RUST, RUN_PYTHON, RUN_CHECKS, READ_ONLY,
            r"^mkdir -p (rust_app|reports|verify)(/\S*)?$", r"^rm (-f )?(verify|rust_app)/[\w/.-]+$",
        ],
    },
    "analyst": {"write": [], "bash": []},
}

# 사람이 소유하는 것. 샌드박스에서 쓰기를 막고, 게이트의 기준 고정 검사로 다시 확인한다
PROTECTED = ["python_src", "tests", "contracts", "automation", ".rustify", "baseline.lock",
             "pyproject.toml", "uv.lock", ".python-version"]
CRATES_DOMAINS = ["crates.io", "index.crates.io", "static.crates.io"]

FILE_WRITE_TOOLS = {"Write", "Edit", "NotebookEdit", "MultiEdit"}
FILE_READ_TOOLS = {"Read", "Glob", "Grep"}


def sandbox_settings(workspace: Path, deny_read: list[Path], allow_crates: bool) -> dict[str, Any]:
    home = Path.home()
    return {
        "enabled": True,
        "autoAllowBashIfSandboxed": False,
        "allowUnsandboxedCommands": False,
        "failIfUnavailable": True,  # 샌드박스를 못 쓰면 시작하지 않는다(12-4 실패 조건)
        "network": {"allowedDomains": CRATES_DOMAINS if allow_crates else []},
        "filesystem": {
            "allowWrite": [str(home / ".cache" / "uv"), str(home / ".cargo" / "registry"),
                           str(home / ".cargo" / ".package-cache"), str(home / ".cargo" / "git")],
            "denyWrite": [str(workspace / name) for name in PROTECTED],
            "denyRead": [str(p) for p in deny_read],
        },
    }


@dataclass
class Policy:
    workspace: Path
    role: str
    audit_path: Path
    read_roots: list[Path] = field(default_factory=list)

    def _inside(self, path: Path, roots: list[Path]) -> bool:
        resolved = path.resolve()
        return any(resolved == root or root in resolved.parents for root in roots)

    def _abs(self, raw: str) -> Path:
        path = Path(raw)
        return path if path.is_absolute() else self.workspace / path

    def check(self, tool: str, tool_input: dict[str, Any]) -> str | None:
        rules = ROLES[self.role]
        if tool in FILE_WRITE_TOOLS:
            target = self._abs(tool_input.get("file_path") or tool_input.get("notebook_path") or "").resolve()
            if not self._inside(target, [self.workspace.resolve()]):
                return "작업 폴더 밖에는 쓸 수 없습니다"
            rel = target.relative_to(self.workspace.resolve()).as_posix()
            if not any(rel.startswith(prefix) for prefix in rules["write"]):
                return f"{rel} 에는 쓸 수 없습니다(쓸 수 있는 곳: {', '.join(rules['write']) or '없음'})"
            return None
        if tool in FILE_READ_TOOLS:
            raw = tool_input.get("file_path") or tool_input.get("path") or str(self.workspace)
            if not self._inside(self._abs(raw), [self.workspace.resolve(), *self.read_roots]):
                return f"작업 폴더 밖({raw})은 읽을 수 없습니다"
            return None
        if tool == "Bash":
            return self.check_command(tool_input.get("command", ""))
        if tool in {"TodoWrite", "StructuredOutput"}:
            return None
        return f"{tool} 도구는 허용하지 않습니다"

    def check_command(self, command: str) -> str | None:
        rules = ROLES[self.role]["bash"]
        if not rules:
            return "셸 명령을 실행할 수 없습니다"
        cleaned = command.replace("2>&1", "").strip()
        if SHELL_CHAINING.search(cleaned):
            return "명령을 잇거나(; && ||) 파일로 쓰는(> <) 구문, 명령 치환은 허용하지 않습니다. 한 번에 명령 하나만 실행하세요"
        first, *filters = [part.strip() for part in cleaned.split("|")]
        if re.match(r"^find\b", first) and re.search(r"\s-(exec|execdir|delete|ok|fprint)", first):
            return "find 의 -exec, -delete 는 허용하지 않습니다"
        if not any(re.match(rule, first) for rule in rules):
            return f"허용 목록에 없는 명령입니다: {first[:80]}"
        outside = self.outside_paths(cleaned)
        if outside:
            return f"작업 폴더 밖 경로는 쓸 수 없습니다: {outside[0][:80]}"
        for part in filters:
            if not PIPE_FILTERS.match(part):
                return f"파이프 뒤에는 읽기 전용 필터(head, tail, grep 등)만 쓸 수 있습니다: {part[:40]}"
        return None

    def outside_paths(self, command: str) -> list[str]:
        try:
            tokens = shlex.split(command)
        except ValueError:
            return [command]
        roots = [self.workspace.resolve(), *self.read_roots, Path("/dev/null")]
        found = []
        for token in tokens:
            value = token.split("=", 1)[1] if token.startswith("--") and "=" in token else token
            if value.startswith(("/", "~")) or ".." in Path(value).parts:
                if not self._inside(self._abs(str(Path(value).expanduser())), roots):
                    found.append(value)
        return found

    async def hook(self, input_data: dict[str, Any], tool_use_id: str | None, context: Any) -> dict[str, Any]:
        tool_input = input_data.get("tool_input") or {}
        reason = self.check(input_data["tool_name"], tool_input)
        summary = tool_input.get("command") or tool_input.get("file_path") or tool_input.get("pattern") or ""
        with self.audit_path.open("a", encoding="utf-8") as fp:
            fp.write(json.dumps({"ts": round(time.time(), 3), "role": self.role, "tool": input_data["tool_name"],
                                 "input": str(summary)[:200], "decision": "deny" if reason else "allow",
                                 "reason": reason}, ensure_ascii=False) + "\n")
        if reason is None:
            return {}
        return {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                       "permissionDecisionReason": reason}}
