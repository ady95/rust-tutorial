"""Claude Agent SDK 로 에이전트 세션 하나를 실행하고 모든 메시지를 기록한다 (08-1, 08-5)."""

from __future__ import annotations

import dataclasses
import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from claude_agent_sdk import (
    AgentDefinition,
    AssistantMessage,
    ClaudeAgentOptions,
    HookMatcher,
    ResultMessage,
    SystemMessage,
    ToolUseBlock,
    query,
)

from .policy import Policy

# 책의 실측 버전과 맞추려고 SDK 에 들어 있는 CLI 대신 설치한 Claude Code 를 쓴다
CLI_PATH = os.environ.get("PORTER_CLAUDE_CLI", str(Path.home() / ".local" / "bin" / "claude"))


@dataclass
class SessionResult:
    label: str
    session_id: str | None = None
    subtype: str | None = None
    num_turns: int = 0
    cost_usd: float = 0.0  # 이 세션(이어 실행했으면 대화 전체)의 누적 추정 비용
    duration_s: float = 0.0
    model: str | None = None
    claude_code_version: str | None = None
    tool_calls: dict[str, int] = field(default_factory=dict)
    subagent_calls: dict[str, int] = field(default_factory=dict)
    denials: int = 0
    structured_output: Any = None
    result_text: str | None = None
    model_usage: dict[str, Any] | None = None


def to_jsonable(message: Any) -> dict[str, Any]:
    body = dataclasses.asdict(message) if dataclasses.is_dataclass(message) else {"value": str(message)}
    return {"type": type(message).__name__, **body}


async def run_session(
    *,
    label: str,
    prompt: str,
    workspace: Path,
    policy: Policy,
    log_path: Path,
    system_append: str,
    tools: list[str],
    model: str = "opus",
    max_turns: int = 80,
    max_budget_usd: float = 5.0,
    resume: str | None = None,
    agents: dict[str, AgentDefinition] | None = None,
    output_schema: dict[str, Any] | None = None,
    sandbox: dict[str, Any] | None = None,
) -> SessionResult:
    options = ClaudeAgentOptions(
        cli_path=CLI_PATH,
        cwd=str(workspace),
        model=model,
        system_prompt={"type": "preset", "preset": "claude_code", "append": system_append},
        tools=tools,  # 세션에 보이는 도구 자체를 제한
        allowed_tools=[t for t in tools if t != "Agent"] + (["Agent"] if agents else []),
        permission_mode="dontAsk",  # 허용 목록과 훅이 허용하지 않은 것은 묻지 않고 거부
        hooks={"PreToolUse": [HookMatcher(hooks=[policy.hook])]},
        setting_sources=[],  # 사용자·프로젝트 설정 파일을 읽지 않는다(재현성)
        strict_mcp_config=True,  # 사용자 MCP 서버를 붙이지 않는다
        max_turns=max_turns,
        max_budget_usd=max_budget_usd,
        resume=resume,
        agents=agents,
        output_format={"type": "json_schema", "schema": output_schema} if output_schema else None,
        sandbox=sandbox,  # 셸 명령을 OS 수준에서 가둔다(08-5)
        # 서브에이전트가 또 서브에이전트를 만들지 못하게, 정의하지 않은 기본 서브에이전트(general-purpose)도 끈다
        # VIRTUAL_ENV: 파이프라인을 uv run 으로 띄우면 파이프라인 자신의 가상 환경 경로가 에이전트 셸로 넘어가는데,
        # 샌드박스는 그 경로를 읽지 못하게 막으므로 PyO3 빌드 등이 실패했다(11-3). 작업 폴더의 가상 환경을 가리키게 한다
        env={"CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH": "1", "CLAUDE_AGENT_SDK_DISABLE_BUILTIN_AGENTS": "1",
             "VIRTUAL_ENV": str(workspace / ".venv")},
    )
    result = SessionResult(label=label)
    started = time.monotonic()
    with log_path.open("a", encoding="utf-8") as log:
        log.write(json.dumps({"type": "porter_session_start", "label": label, "resume": resume,
                              "ts": round(time.time(), 3)}, ensure_ascii=False) + "\n")
        try:
            async for message in query(prompt=prompt, options=options):
                log.write(json.dumps(to_jsonable(message), ensure_ascii=False, default=str) + "\n")
                collect(result, message)
        except Exception as err:  # query() 는 오류 결과를 낸 뒤 예외를 던진다
            log.write(json.dumps({"type": "porter_error", "error": str(err)[:500]}, ensure_ascii=False) + "\n")
            if result.subtype is None:
                result.subtype = f"exception: {type(err).__name__}"
    result.duration_s = round(time.monotonic() - started, 1)
    return result


def collect(result: SessionResult, message: Any) -> None:
    if isinstance(message, SystemMessage) and message.subtype == "init":
        result.session_id = message.data.get("session_id")
        result.model = message.data.get("model")
        result.claude_code_version = message.data.get("claude_code_version")
    elif isinstance(message, AssistantMessage):
        for block in message.content:
            if isinstance(block, ToolUseBlock):
                result.tool_calls[block.name] = result.tool_calls.get(block.name, 0) + 1
                if block.name in {"Agent", "Task"}:
                    kind = str(block.input.get("subagent_type"))
                    result.subagent_calls[kind] = result.subagent_calls.get(kind, 0) + 1
    elif isinstance(message, ResultMessage):
        result.session_id = message.session_id
        result.subtype = message.subtype
        result.num_turns = message.num_turns
        result.cost_usd = message.total_cost_usd or 0.0
        result.denials = len(message.permission_denials or [])
        result.structured_output = message.structured_output
        result.result_text = message.result
        result.model_usage = message.model_usage
