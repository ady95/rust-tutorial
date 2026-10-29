"""에이전트 엔진 (12-2, 12-5). 이식 단계는 엔진에 지시문을 주고 결과(SessionResult)만 받는다.

- ClaudeEngine: Claude Agent SDK. 도구 호출마다 정책 훅(policy.py)이 판정하고, 셸 명령은 샌드박스 안에서 실행
- CodexEngine: Codex CLI 의 비대화형 실행(codex exec --json). Codex 자체 샌드박스(workspace-write)에 맡긴다

두 엔진의 차이(권한 모델, 비용 표시)는 12-5 에서 비교한다. 기록은 기록 폴더의 events.jsonl 에 남기되,
측정 환경 정보(설치된 도구·스킬 목록, 홈 경로)는 지운다(12-4).
"""

from __future__ import annotations

import asyncio
import dataclasses
import json
import os
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .policy import Policy, sandbox_settings

HOME = str(Path.home())
INIT_DROP = {"tools", "slash_commands", "agents", "skills", "plugins", "mcp_servers", "memory_paths",
             "scratchpad_path", "messaging_socket_path", "startup_timing", "terminal_slash_commands",
             "output_style", "betas", "fast_mode_state", "capabilities", "plugin_errors"}


@dataclass
class SessionResult:
    engine: str
    label: str
    session_id: str | None = None
    status: str | None = None  # success | error_max_turns | error_max_budget_usd | error | exception: ...
    num_turns: int = 0
    cost_usd: float | None = None  # Claude: SDK 추정치(이어 실행하면 대화 누적). Codex: 구독 요금이라 없음
    tokens: dict[str, int] = field(default_factory=dict)
    duration_s: float = 0.0
    model: str | None = None
    agent_version: str | None = None
    tool_calls: dict[str, int] = field(default_factory=dict)
    denials: int = 0
    structured_output: Any = None
    final_text: str | None = None


def log_line(log: Any, row: dict) -> None:
    log.write(json.dumps(row, ensure_ascii=False, default=str).replace(HOME, "~") + "\n")


class ClaudeEngine:
    name = "claude"

    def __init__(self, model: str, cli_path: str | None = None) -> None:
        self.model = model
        self.cli_path = cli_path or os.environ.get("RUSTIFY_CLAUDE_CLI", str(Path.home() / ".local" / "bin" / "claude"))

    async def session(self, *, label: str, prompt: str, system: str, workspace: Path, log_path: Path,
                      audit_path: Path, role: str, read_roots: list[Path], deny_read: list[Path],
                      allow_crates: bool, budget_usd: float, max_turns: int, resume: str | None = None,
                      output_schema: dict | None = None) -> SessionResult:
        from claude_agent_sdk import (AssistantMessage, ClaudeAgentOptions, HookMatcher, ResultMessage,
                                      SystemMessage, ToolUseBlock, query)

        policy = Policy(workspace, role, audit_path, read_roots)
        tools = ["Read", "Glob", "Grep"] if role == "analyst" else ["Read", "Glob", "Grep", "Write", "Edit", "Bash", "TodoWrite"]
        options = ClaudeAgentOptions(
            cli_path=self.cli_path, cwd=str(workspace), model=self.model,
            system_prompt={"type": "preset", "preset": "claude_code", "append": system},
            tools=tools, allowed_tools=tools, permission_mode="dontAsk",
            hooks={"PreToolUse": [HookMatcher(hooks=[policy.hook])]},
            setting_sources=[], strict_mcp_config=True, max_turns=max_turns, max_budget_usd=budget_usd,
            resume=resume, output_format={"type": "json_schema", "schema": output_schema} if output_schema else None,
            sandbox=None if role == "analyst" else sandbox_settings(workspace, deny_read, allow_crates),
            env={"CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH": "1", "CLAUDE_AGENT_SDK_DISABLE_BUILTIN_AGENTS": "1",
                 "VIRTUAL_ENV": str(workspace / ".venv")},
        )
        result = SessionResult(engine=self.name, label=label)
        started = time.monotonic()
        with log_path.open("a", encoding="utf-8") as log:
            log_line(log, {"type": "rustify_session_start", "engine": self.name, "label": label, "resume": resume})
            try:
                async for message in query(prompt=prompt, options=options):
                    row = {"type": type(message).__name__, **dataclasses.asdict(message)}
                    if isinstance(message, SystemMessage) and message.subtype == "init":
                        row["data"] = {k: v for k, v in message.data.items() if k not in INIT_DROP}
                        result.session_id = message.data.get("session_id")
                        result.model = message.data.get("model")
                        result.agent_version = message.data.get("claude_code_version")
                    log_line(log, row)
                    if isinstance(message, AssistantMessage):
                        for block in message.content:
                            if isinstance(block, ToolUseBlock):
                                result.tool_calls[block.name] = result.tool_calls.get(block.name, 0) + 1
                    elif isinstance(message, ResultMessage):
                        result.session_id = message.session_id
                        result.status = message.subtype
                        result.num_turns = message.num_turns
                        result.cost_usd = message.total_cost_usd or 0.0
                        result.denials = len(message.permission_denials or [])
                        result.structured_output = message.structured_output
                        result.final_text = message.result
                        usage = message.usage or {}
                        result.tokens = {k: int(usage.get(k) or 0) for k in
                                         ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens",
                                          "output_tokens")}
            except Exception as err:  # query() 는 오류 결과를 낸 뒤 예외를 던진다
                log_line(log, {"type": "rustify_error", "error": str(err)[:500]})
                if result.status is None:
                    result.status = f"exception: {type(err).__name__}"
        result.duration_s = round(time.monotonic() - started, 1)
        return result


class CodexEngine:
    """codex exec 를 하위 프로세스로 실행한다. 정책 훅이 없으므로 사람의 파일 보호는 게이트의 기준 고정 검사가 맡는다."""

    name = "codex"

    def __init__(self, model: str | None, cli_path: str | None = None) -> None:
        self.model = model
        self.cli_path = cli_path or os.environ.get("RUSTIFY_CODEX_CLI") or shutil.which("codex") or "codex"

    def command(self, workspace: Path, allow_crates: bool, resume: str | None, prompt: str) -> list[str]:
        cmd = [self.cli_path, "exec"]
        if resume:
            cmd += ["resume", resume]
        cmd += ["--json", "--skip-git-repo-check", "--sandbox", "workspace-write", "--cd", str(workspace),
                "-c", f"sandbox_workspace_write.network_access={'true' if allow_crates else 'false'}"]
        if self.model:
            cmd += ["--model", self.model]
        return cmd + [prompt]

    async def session(self, *, label: str, prompt: str, system: str, workspace: Path, log_path: Path,
                      audit_path: Path, role: str, read_roots: list[Path], deny_read: list[Path],
                      allow_crates: bool, budget_usd: float, max_turns: int, resume: str | None = None,
                      output_schema: dict | None = None) -> SessionResult:
        result = SessionResult(engine=self.name, label=label, model=self.model)
        full_prompt = prompt if resume else system + "\n\n" + prompt  # Codex 에는 시스템 지시문 자리가 없어 앞에 붙인다
        env = dict(os.environ)
        env.pop("VIRTUAL_ENV", None)
        # 샌드박스가 작업 폴더 밖 쓰기를 막으므로 Cargo 의 내려받기 캐시를 작업 폴더 안에 둔다
        env["CARGO_HOME"] = str(workspace / ".cargo-home")
        (workspace / ".cargo-home").mkdir(exist_ok=True)
        cargo_bin = Path.home() / ".cargo" / "bin"
        env["PATH"] = f"{cargo_bin}:{Path.home() / '.local' / 'bin'}:{env.get('PATH', '')}"
        env["RUSTUP_HOME"] = env.get("RUSTUP_HOME", str(Path.home() / ".rustup"))
        started = time.monotonic()
        proc = await asyncio.create_subprocess_exec(
            *self.command(workspace, allow_crates, resume, full_prompt), cwd=workspace, env=env,
            stdin=asyncio.subprocess.DEVNULL, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            limit=1 << 24)
        with log_path.open("a", encoding="utf-8") as log:
            log_line(log, {"type": "rustify_session_start", "engine": self.name, "label": label, "resume": resume})
            assert proc.stdout is not None
            async for raw in proc.stdout:
                try:
                    event = json.loads(raw)
                except json.JSONDecodeError:
                    log_line(log, {"type": "rustify_stdout", "text": raw.decode("utf-8", "replace")[:2000]})
                    continue
                log_line(log, event)
                self.collect(result, event)
            stderr = (await proc.stderr.read()).decode("utf-8", "replace") if proc.stderr else ""
            code = await proc.wait()
            if stderr.strip():
                log_line(log, {"type": "rustify_stderr", "text": stderr[-4000:]})
        if result.status is None:
            result.status = "success" if code == 0 else f"error: exit {code}"
        result.duration_s = round(time.monotonic() - started, 1)
        return result

    @staticmethod
    def collect(result: SessionResult, event: dict) -> None:
        kind = event.get("type")
        if kind == "thread.started":
            result.session_id = event.get("thread_id")
        elif kind == "turn.completed":
            result.num_turns += 1
            for key, value in (event.get("usage") or {}).items():
                if isinstance(value, int):
                    result.tokens[key] = result.tokens.get(key, 0) + value
        elif kind == "turn.failed":
            result.status = "error: " + str((event.get("error") or {}).get("message", ""))[:200]
        elif kind == "item.completed":
            item = event.get("item") or {}
            item_type = item.get("type") or item.get("item_type") or "unknown"
            result.tool_calls[item_type] = result.tool_calls.get(item_type, 0) + 1
            if item_type in ("agent_message", "assistant_message"):
                result.final_text = item.get("text")


def make_engine(name: str, model: str | None) -> ClaudeEngine | CodexEngine:
    if name == "claude":
        return ClaudeEngine(model or "sonnet")
    if name == "codex":
        return CodexEngine(model)
    raise SystemExit(f"알 수 없는 엔진: {name}")
