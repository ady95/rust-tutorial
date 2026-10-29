"""11-3: 에이전트에게 logstat 의 부분 이식(PyO3 확장 모듈)을 맡기고, 파이프라인이 직접 게이트를 실행한다.

8장 파이프라인(ch08/porter)의 세션·정책·샌드박스를 쓴다. 작업 폴더는 ch09/logstat 프로젝트이고,
09장의 전체 이식 소스를 port/rust_reference/ 에 읽기 전용 참고로 넣는다.

사용법 (ch08/porter 에서):
  uv run python ../../ch11/partial/run_partial.py --run ch11_partial --model sonnet --budget 6 --max-rounds 3
"""

from __future__ import annotations

import argparse
import asyncio
import shutil
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "ch08" / "porter"))

import porter  # noqa: E402
from porter_lib import gate as gate_mod  # noqa: E402
from porter_lib import prompts  # noqa: E402
from porter_lib.agent import run_session  # noqa: E402
from porter_lib.policy import CRATES_DOMAINS, Policy, sandbox_settings  # noqa: E402

WRAPPER = '#!/bin/sh\nHERE="$(cd "$(dirname "$0")" && pwd)"\nexec "$HERE/../.venv/bin/python" "$HERE/{name}.py" "$@"\n'


def prepare(run: str) -> Path:
    workspace = porter.prepare_workspace(REPO / "ch09" / "logstat", run, None)
    reference = workspace / "port" / "rust_reference"
    shutil.copytree(porter.HERE / "runs" / "ch09_port" / "workspace" / "rust_app" / "src", reference / "src")
    shutil.copy2(porter.HERE / "runs" / "ch09_port" / "workspace" / "rust_app" / "Cargo.toml", reference / "Cargo.toml")
    (workspace / "ext").mkdir()
    for name in ("logstat_v1", "logstat_v2"):
        path = workspace / "ext" / name
        path.write_text(WRAPPER.format(name=name), encoding="utf-8")
        path.chmod(0o755)
    (workspace / "verify").mkdir()
    subprocess.run(["uv", "pip", "install", "-q", "--python", str(workspace / ".venv"), "maturin>=1.9,<2"],
                   cwd=workspace, check=True)
    return workspace


def run_gate(workspace: Path) -> gate_mod.GateResult:
    import random

    seed = random.randrange(1, 2**31)
    toml = ["--manifest-path", "rust_ext/Cargo.toml"]
    steps = [gate_mod.run_step("baseline", [sys.executable, ".porter/baseline.py", "check"], workspace)]
    if not steps[0].ok:
        return gate_mod.GateResult(False, seed, steps, protected_changed=True)
    steps.append(gate_mod.run_step("fmt", ["cargo", "fmt", *toml, "--", "--check"], workspace))
    steps.append(gate_mod.run_step("clippy", ["cargo", "clippy", *toml, "--", "-D", "warnings"], workspace))
    build = gate_mod.run_step("maturin", [".venv/bin/maturin", "develop", "--release", "-q", "-m", "rust_ext/Cargo.toml"],
                              workspace)
    steps.append(build)
    for v in ("v1", "v2"):
        if not build.ok:
            break
        steps.append(gate_mod.run_step(f"compare-{v}", ["uv", "run", "python", "automation/compare.py", "--rust",
                                                        f"ext/logstat_{v}"], workspace))
        steps.append(gate_mod.run_step(f"fuzz-{v}", ["uv", "run", "python", "automation/fuzz.py", "--rust",
                                                     f"ext/logstat_{v}", "--examples", "1000", "--seed", str(seed)],
                                       workspace))
    return gate_mod.GateResult(all(s.ok for s in steps) and len(steps) == 8, seed, steps)


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", required=True)
    parser.add_argument("--model", default="sonnet")
    parser.add_argument("--budget", type=float, default=6.0)
    parser.add_argument("--max-rounds", type=int, default=3)
    args = parser.parse_args()
    workspace = prepare(args.run)
    out = porter.run_dir(args.run)
    for name in ("audit.jsonl", "events.jsonl", "sessions.jsonl"):
        (out / name).unlink(missing_ok=True)
    policy = Policy(workspace, "implementer_ext", out / "audit.jsonl", porter.read_roots())
    sandbox = sandbox_settings(workspace, porter.deny_read_paths(workspace), CRATES_DOMAINS)
    system = prompts.IMPLEMENTER.replace("rust_app/ 과 reports/ 에만", "rust_ext/, ext/, reports/, verify/ 에만") \
        + prompts.IMPLEMENTER_V2_EXTRA + prompts.CRATES_NOTE
    session_id, spent, total_before = None, 0.0, 0.0
    prompt = (HERE / "prompts" / "partial.md").read_text(encoding="utf-8")
    for round_no in range(1, args.max_rounds + 1):
        result = await run_session(
            label=f"round{round_no}", prompt=prompt, workspace=workspace, policy=policy, log_path=out / "events.jsonl",
            system_append=system, tools=porter.FILE_TOOLS, model=args.model, max_turns=100,
            max_budget_usd=max(args.budget - spent, 0.1), resume=session_id, sandbox=sandbox)
        cost = result.cost_usd - total_before if session_id else result.cost_usd
        total_before, spent, session_id = result.cost_usd, spent + cost, result.session_id or session_id
        gate = run_gate(workspace)
        gate_mod.save(gate, out / f"gate_round{round_no}.json")
        porter.append_jsonl(out / "sessions.jsonl", asdict(result) | {
            "round": round_no, "round_cost_usd": round(cost, 4), "gate_ok": gate.ok, "gate_failing": gate.failing(),
            "fuzz_seed": gate.fuzz_seed})
        print(f"round {round_no}: {result.subtype}, {result.num_turns}턴, ${cost:.4f}, "
              f"게이트 {'통과' if gate.ok else '실패 ' + ','.join(gate.failing())}")
        if gate.ok or gate.protected_changed or spent >= args.budget:
            break
        prompt = prompts.FIX_PROMPT.format(feedback=gate_mod.feedback(gate))
    for sub in ("rust_ext", "ext", "reports", "verify"):
        dst = out / "workspace" / sub
        if dst.exists():
            shutil.rmtree(dst)
        if (workspace / sub).exists():
            shutil.copytree(workspace / sub, dst, symlinks=True, ignore=shutil.ignore_patterns("target", "__pycache__"))
    print(f"total ${spent:.4f}")
    return 0 if gate.ok else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
