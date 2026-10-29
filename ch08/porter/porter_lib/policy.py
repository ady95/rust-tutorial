"""도구 호출 정책 (08-5). PreToolUse 훅 하나로 모든 도구 호출을 검사하고 감사 기록(audit.jsonl)을 남긴다.

역할(role)마다 쓸 수 있는 경로와 실행할 수 있는 명령이 다르다.
- 서브에이전트 안에서 호출되면 훅 입력의 agent_type 이 그 서브에이전트 이름이다
- 메인 에이전트의 역할은 실행할 때 정한다(단일 모드는 implementer, 분리 모드는 coordinator)

권한 설정(allowed_tools, permission_mode)보다 이 훅이 먼저 판정한다. 훅이 deny 하면 어떤 모드에서도 실행되지 않는다.
"""

from __future__ import annotations

import json
import re
import shlex
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# 명령 뒤에 파이프로 붙여도 되는 읽기 전용 필터
PIPE_FILTERS = re.compile(r"^(head|tail|grep|wc|sort|uniq|cut|od|xxd)\b")
# 명령을 잇거나 파일로 쓰는 셸 구문은 허용하지 않는다 (2>&1 만 예외)
SHELL_CHAINING = re.compile(r";|&&|\|\||`|\$\(|>|<")

READ_ONLY_COMMANDS = r"^(ls|cat|head|tail|wc|od|xxd|diff|cmp|grep|rg|find|file|stat)\b"
RUN_RUST = r"^(\./)?rust_app/target/(release|debug)/[\w-]+(\s|$)"
RUN_PYTHON_REF = r"^(python3|uv run python) python_src/[\w-]+\.py(\s|$)"
RUN_CHECKS = r"^(python3|uv run python) automation/(compare|scenarios|fuzz)\.py(\s|$)"

ROLES: dict[str, dict[str, list[str]]] = {
    # 쓰기 가능한 경로(작업 폴더 기준 접두어)와 Bash 허용 정규식
    "implementer": {
        "write": ["rust_app/", "reports/"],
        "bash": [
            r"^cargo (new|init|build|check|test|run|clippy|fmt|add|tree|metadata)(\s|$)",
            RUN_RUST, RUN_PYTHON_REF, RUN_CHECKS, READ_ONLY_COMMANDS, r"^mkdir -p (rust_app|reports)(/\S*)?$",
        ],
    },
    # 정책 2판(08-3 single1 이후): 에이전트가 verify/ 에 쓴 검증 스크립트를 실행할 수 있다.
    # 인터프리터를 허용하면 그 스크립트는 무엇이든 할 수 있으므로 샌드박스(sandbox_settings)와 함께만 쓴다
    "implementer_v2": {
        "write": ["rust_app/", "reports/", "verify/"],
        "bash": [
            r"^cargo (new|init|build|check|test|run|clippy|fmt|add|tree|metadata)(\s|$)",
            r"^(python3|uv run python) verify/[\w/.-]+\.py(\s|$)",
            RUN_RUST, RUN_PYTHON_REF, RUN_CHECKS, READ_ONLY_COMMANDS,
            r"^mkdir -p (rust_app|reports|verify)(/\S*)?$", r"^rm (-f )?(verify|rust_app)/[\w/.-]+$",
        ],
    },
    # 11장 부분 이식: Python 은 그대로 두고 Rust 확장 모듈(rust_ext/)과 그것을 쓰는 Python 진입점(ext/)을 만든다
    "implementer_ext": {
        "write": ["rust_ext/", "ext/", "reports/", "verify/"],
        "bash": [
            r"^cargo (build|check|test|clippy|fmt|add|tree|metadata)(\s|$)",
            r"^(\.venv/bin/)?maturin (develop|build)(\s|$)",
            r"^(\.venv/bin/python|python3|uv run python) (verify|ext)/[\w/.-]+\.py(\s|$)",
            r"^(\./)?ext/logstat_v[12](\s|$)",
            RUN_PYTHON_REF, RUN_CHECKS, READ_ONLY_COMMANDS,
            r"^mkdir -p (rust_ext|ext|reports|verify)(/\S*)?$", r"^rm (-f )?(verify|ext|rust_ext)/[\w/.-]+$",
        ],
    },
    "verifier": {
        "write": ["verify/"],
        "bash": [
            r"^cargo build --release(\s|$)",
            r"^(python3|uv run python) verify/[\w/.-]+\.py(\s|$)",
            RUN_RUST, RUN_PYTHON_REF, RUN_CHECKS, READ_ONLY_COMMANDS, r"^mkdir -p verify(/\S*)?$",
            r"^rm (-f )?verify/[\w/.-]+$",
        ],
    },
    "coordinator": {"write": [], "bash": []},
    "analyst": {"write": [], "bash": []},
}

PROTECTED = ["python_src", "tests", "contracts", "automation", "port", ".porter", "baseline.lock",
             "pyproject.toml", "uv.lock", ".python-version"]


# 외부 크레이트를 받을 때 여는 도메인(09장). Cargo 레지스트리만 허용한다
CRATES_DOMAINS = ["crates.io", "index.crates.io", "static.crates.io"]


def sandbox_settings(workspace: Path, deny_read: list[Path], allowed_domains: list[str] | None = None) -> dict[str, Any]:
    """셸 명령용 샌드박스 설정(bubblewrap). 쓰기는 작업 폴더(사람의 파일 제외)와 캐시로, 네트워크는 기본 차단."""
    home = Path.home()
    return {
        "enabled": True,
        "autoAllowBashIfSandboxed": False,  # 샌드박스 안이어도 허용 여부는 훅·허용 목록이 정한다
        "allowUnsandboxedCommands": False,  # 샌드박스 밖으로 다시 실행하는 길을 막는다
        "failIfUnavailable": True,  # 샌드박스를 못 쓰면 조용히 넘어가지 말고 시작하지 않는다
        "network": {"allowedDomains": list(allowed_domains or [])},
        "filesystem": {
            "allowWrite": [str(home / ".cache" / "uv"), str(home / ".cargo" / "registry"),
                           str(home / ".cargo" / ".package-cache"), str(home / ".cargo" / "git")],
            "denyWrite": [str(workspace / name) for name in PROTECTED],
            "denyRead": [str(p) for p in deny_read],
        },
    }


FILE_WRITE_TOOLS = {"Write", "Edit", "NotebookEdit", "MultiEdit"}
FILE_READ_TOOLS = {"Read", "Glob", "Grep"}


@dataclass
class Policy:
    workspace: Path
    main_role: str
    audit_path: Path
    read_roots: list[Path] = field(default_factory=list)  # 작업 폴더 밖에서 읽어도 되는 곳
    role_alias: dict[str, str] = field(default_factory=dict)  # 서브에이전트 이름 → 적용할 역할(정책 판)

    def _inside(self, path: Path, roots: list[Path]) -> bool:
        resolved = path.resolve()
        return any(resolved == root or root in resolved.parents for root in roots)

    def _abs(self, raw: str) -> Path:
        path = Path(raw)
        return path if path.is_absolute() else self.workspace / path

    def check(self, role: str, tool: str, tool_input: dict[str, Any]) -> str | None:
        """허용이면 None, 거부면 이유 문자열."""
        rules = ROLES[role]
        if tool in FILE_WRITE_TOOLS:
            raw = tool_input.get("file_path") or tool_input.get("notebook_path") or ""
            target = self._abs(raw).resolve()
            if not self._inside(target, [self.workspace.resolve()]):
                return f"{role}: 작업 폴더 밖에는 쓸 수 없습니다"
            rel = target.relative_to(self.workspace.resolve()).as_posix()
            if not any(rel.startswith(prefix) for prefix in rules["write"]):
                allowed = ", ".join(rules["write"]) or "없음"
                return f"{role}: {rel} 에는 쓸 수 없습니다(쓸 수 있는 곳: {allowed})"
            return None
        if tool in FILE_READ_TOOLS:
            raw = tool_input.get("file_path") or tool_input.get("path") or str(self.workspace)
            if not self._inside(self._abs(raw), [self.workspace.resolve(), *self.read_roots]):
                return f"{role}: 작업 폴더 밖({raw})은 읽을 수 없습니다"
            return None
        if tool == "Bash":
            return self.check_command(role, tool_input.get("command", ""))
        if tool in {"Agent", "Task"}:
            return None if role == "coordinator" else f"{role}: 서브에이전트를 만들 수 없습니다"
        if tool in {"TodoWrite", "StructuredOutput"}:
            return None
        return f"{role}: {tool} 도구는 허용하지 않습니다"

    def check_command(self, role: str, command: str) -> str | None:
        rules = ROLES[role]["bash"]
        if not rules:
            return f"{role}: 셸 명령을 실행할 수 없습니다"
        cleaned = command.replace("2>&1", "").strip()
        if SHELL_CHAINING.search(cleaned):
            return "명령을 잇거나(; && ||) 파일로 쓰는(> <) 구문, 명령 치환은 허용하지 않습니다. 한 번에 명령 하나만 실행하세요"
        first, *filters = [part.strip() for part in cleaned.split("|")]
        if re.match(r"^find\b", first) and re.search(r"\s-(exec|execdir|delete|ok|fprint)", first):
            return "find 의 -exec, -delete 는 허용하지 않습니다"
        if not any(re.match(rule, first) for rule in rules):
            return f"{role}: 허용 목록에 없는 명령입니다: {first[:80]}"
        outside = self.outside_paths(cleaned)
        if outside:
            return f"{role}: 작업 폴더 밖 경로는 쓸 수 없습니다: {outside[0][:80]}"
        for part in filters:
            if not PIPE_FILTERS.match(part):
                return f"파이프 뒤에는 읽기 전용 필터(head, tail, grep 등)만 쓸 수 있습니다: {part[:40]}"
        return None

    def outside_paths(self, command: str) -> list[str]:
        """명령 인자 중 작업 폴더·읽기 허용 폴더 밖을 가리키는 경로(절대 경로, ~, ..)."""
        try:
            tokens = shlex.split(command)
        except ValueError:
            return [command]
        roots = [self.workspace.resolve(), *self.read_roots, Path("/dev/null"), Path("/dev/full")]
        found = []
        for token in tokens:
            value = token.split("=", 1)[1] if token.startswith("--") and "=" in token else token
            if value.startswith(("/", "~")) or ".." in Path(value).parts:
                if not self._inside(self._abs(str(Path(value).expanduser())), roots):
                    found.append(value)
        return found

    def audit(self, row: dict[str, Any]) -> None:
        with self.audit_path.open("a", encoding="utf-8") as fp:
            fp.write(json.dumps(row, ensure_ascii=False) + "\n")

    async def hook(self, input_data: dict[str, Any], tool_use_id: str | None, context: Any) -> dict[str, Any]:
        role = input_data.get("agent_type") or self.main_role
        role = self.role_alias.get(role, role)
        if role not in ROLES:  # 정의하지 않은 서브에이전트(general-purpose 등)
            reason = f"정의되지 않은 역할({role})의 도구 호출은 허용하지 않습니다"
        else:
            reason = self.check(role, input_data["tool_name"], input_data.get("tool_input") or {})
        tool_input = input_data.get("tool_input") or {}
        summary = tool_input.get("command") or tool_input.get("file_path") or tool_input.get("pattern") \
            or tool_input.get("subagent_type") or ""
        self.audit({"ts": round(time.time(), 3), "role": role, "tool": input_data["tool_name"],
                    "input": str(summary)[:200], "decision": "deny" if reason else "allow", "reason": reason})
        if reason is None:
            return {}
        return {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                       "permissionDecisionReason": reason}}
