"""08-1: 같은 일을 Claude Agent SDK(Python)로. 도구 호출마다 훅이 불리는 것도 확인한다.

사용법 (ch08/porter 에서): uv run python examples/sdk_minimal.py ../projects/wordfreq
"""

import asyncio
import json
import sys
from pathlib import Path

from claude_agent_sdk import ClaudeAgentOptions, HookMatcher, ResultMessage, query

SCHEMA = json.loads((Path(__file__).parent / "schema_functions.json").read_text(encoding="utf-8"))
CLI = str(Path.home() / ".local" / "bin" / "claude")  # 설치한 Claude Code 를 쓴다(SDK 에 든 CLI 대신)


async def log_tool(input_data, tool_use_id, context):
    print(f"  tool: {input_data['tool_name']} {json.dumps(input_data['tool_input'], ensure_ascii=False)[:80]}")
    return {}  # 빈 객체 = 허용


async def main(project: str) -> None:
    options = ClaudeAgentOptions(
        cli_path=CLI,
        cwd=project,
        model="sonnet",
        tools=["Read", "Glob", "Grep"],
        allowed_tools=["Read", "Glob", "Grep"],
        permission_mode="dontAsk",
        setting_sources=[],
        strict_mcp_config=True,
        max_turns=10,
        max_budget_usd=0.5,
        output_format={"type": "json_schema", "schema": SCHEMA},
        hooks={"PreToolUse": [HookMatcher(hooks=[log_tool])]},
    )
    prompt = "python_src/ 의 각 함수가 contracts/behavior_spec.md 의 어느 절을 구현하는지 정리해 주세요."
    async for message in query(prompt=prompt, options=options):
        if isinstance(message, ResultMessage):
            print(json.dumps({"subtype": message.subtype, "num_turns": message.num_turns,
                              "duration_ms": message.duration_ms, "total_cost_usd": message.total_cost_usd,
                              "structured_output": message.structured_output}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1]))
