"""기존 이식 결과를 복사해 에이전트에게 '알고리즘만 바꾼 변형'을 만들게 한다 (09-4).

8장 파이프라인(ch08/porter)의 세션·정책·게이트를 그대로 쓴다. 출력은 기준 구현과 같아야 하므로 같은 게이트로 판정한다.

사용법 (ch08/porter 에서):
  uv run python ../../ch09/bench/variant.py --from ch09_port --run ch09_stream \
      --prompt-file ../../ch09/bench/prompts/streaming.md --model sonnet
"""

from __future__ import annotations

import argparse
import asyncio
import json
import shutil
import sys
from dataclasses import asdict
from pathlib import Path

PORTER = Path(__file__).resolve().parents[2] / "ch08" / "porter"
sys.path.insert(0, str(PORTER))

import porter  # noqa: E402
from porter_lib import gate as gate_mod  # noqa: E402
from porter_lib import prompts  # noqa: E402
from porter_lib.agent import run_session  # noqa: E402
from porter_lib.policy import CRATES_DOMAINS, Policy, sandbox_settings  # noqa: E402


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--from", dest="source", required=True, help="복사할 실행 이름(작업 폴더)")
    parser.add_argument("--run", required=True)
    parser.add_argument("--prompt-file", type=Path, required=True)
    parser.add_argument("--model", default="sonnet")
    parser.add_argument("--budget", type=float, default=5.0)
    args = parser.parse_args()

    source = porter.WORK / args.source
    workspace = porter.WORK / args.run
    if workspace.exists():
        shutil.rmtree(workspace)
    shutil.copytree(source, workspace, symlinks=True,
                    ignore=shutil.ignore_patterns("target", ".venv", "__pycache__", "verify"))
    (workspace / "verify").mkdir()
    porter.subprocess.run(["uv", "sync", "-q"], cwd=workspace, check=True)  # 비교 도구 환경(샌드박스 밖에서 미리)
    out = porter.run_dir(args.run)
    manifest = json.loads((workspace / "automation" / "port.json").read_text(encoding="utf-8"))
    policy = Policy(workspace, "implementer_v2", out / "audit.jsonl", porter.read_roots())
    sandbox = sandbox_settings(workspace, porter.deny_read_paths(workspace), CRATES_DOMAINS)
    result = await run_session(
        label="variant", prompt=args.prompt_file.read_text(encoding="utf-8"), workspace=workspace, policy=policy,
        log_path=out / "events.jsonl", system_append=prompts.IMPLEMENTER + prompts.IMPLEMENTER_V2_EXTRA,
        tools=porter.FILE_TOOLS, model=args.model, max_turns=80, max_budget_usd=args.budget, sandbox=sandbox,
    )
    gate = gate_mod.run_gate(workspace, manifest)
    gate_mod.save(gate, out / "gate_round1.json")
    porter.append_jsonl(out / "sessions.jsonl", asdict(result) | {
        "round": 1, "round_cost_usd": round(result.cost_usd, 4), "gate_ok": gate.ok, "gate_failing": gate.failing(),
        "fuzz_seed": gate.fuzz_seed, "from": args.source})
    porter.collect_outputs(workspace, out)
    print(f"variant: {result.subtype}, {result.num_turns}턴, ${result.cost_usd:.4f}, "
          f"게이트 {'통과' if gate.ok else '실패 ' + ','.join(gate.failing())}")
    return 0 if gate.ok else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
