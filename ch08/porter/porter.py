"""Python → Rust 자동 이식 파이프라인 (08장).

    uv run python porter.py analyze <프로젝트> --run <이름>            # 08-2 분석·이식 계획(plan.json)
    uv run python porter.py port <프로젝트> --run <이름> [--plan 파일] [--mode single|split]
                                                                       # 08-3·08-4 생성·검증·수정 루프
    uv run python porter.py heldout --run <이름>                        # 루프가 끝난 뒤 숨긴 평가
    uv run python porter.py report --run <이름>                         # 08-6 보고서·산출물

실행마다 작업 폴더(~/work/ch08_ws/<이름>)를 새로 만들고, 기록은 runs/<이름>/ 에 남긴다.
Linux·WSL 기준. 에이전트 인증은 Claude Code 로그인(또는 ANTHROPIC_API_KEY)을 그대로 쓴다.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import shutil
import subprocess
import sys
import time
from dataclasses import asdict
from pathlib import Path

from claude_agent_sdk import AgentDefinition

from porter_lib import gate as gate_mod
from porter_lib import prompts
from porter_lib.agent import run_session
from porter_lib.policy import CRATES_DOMAINS, Policy, sandbox_settings
from porter_lib.report import write_report

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
WORK = Path.home() / "work" / "ch08_ws"
FILE_TOOLS = ["Read", "Glob", "Grep", "Write", "Edit", "Bash", "TodoWrite"]


def read_roots() -> list[Path]:
    """작업 폴더 밖에서 읽기를 허용하는 곳: Python·Rust 표준 라이브러리 소스."""
    roots = [Path(sys.base_prefix) / "lib" / f"python{sys.version_info.major}.{sys.version_info.minor}"]
    roots += sorted((Path.home() / ".rustup" / "toolchains").glob("*/lib/rustlib/src"))
    return [r.resolve() for r in roots if r.exists()]


def deny_read_paths(workspace: Path) -> list[Path]:
    """샌드박스 안의 셸 명령이 읽지 못하게 할 곳: 인증 정보, 이전 장의 구현, 다른 실행의 작업 폴더."""
    home = Path.home()
    paths = [home / ".ssh", home / ".claude", home / ".claude.json", home / "work" / "rust-tutorial",
             home / "work" / "ch07_bin", home / "work" / "ch07_runs", home / "work" / "sdk_probe"]
    paths += [p for p in WORK.iterdir() if p.is_dir() and p != workspace]
    return [p for p in paths if p.exists()]


def prepare_workspace(project: Path, name: str, plan: Path | None) -> Path:
    workspace = WORK / name
    if workspace.exists():
        shutil.rmtree(workspace)
    ignore = shutil.ignore_patterns(".venv", "__pycache__", ".pytest_cache", ".hypothesis", "rust_app", "reports")
    shutil.copytree(project, workspace, ignore=ignore)
    (workspace / ".porter").mkdir()
    shutil.copy2(REPO / "tools" / "baseline.py", workspace / ".porter" / "baseline.py")
    (workspace / "reports").mkdir()
    if plan:
        (workspace / "port").mkdir()
        shutil.copy2(plan, workspace / "port" / "plan.json")
    subprocess.run(["uv", "sync", "-q"], cwd=workspace, check=True)  # 비교 도구(Hypothesis)용 환경
    check = subprocess.run([sys.executable, ".porter/baseline.py", "check"], cwd=workspace, capture_output=True, text=True)
    if check.returncode != 0:
        raise SystemExit(f"기준 고정 검사 실패(승인되지 않은 프로젝트): {check.stderr}")
    return workspace


def run_dir(name: str) -> Path:
    path = HERE / "runs" / name
    path.mkdir(parents=True, exist_ok=True)
    return path


def append_jsonl(path: Path, row: dict) -> None:
    with path.open("a", encoding="utf-8") as fp:
        fp.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")


async def cmd_analyze(args: argparse.Namespace) -> int:
    out = run_dir(args.run)
    workspace = prepare_workspace(args.project.resolve(), args.run, None)
    policy = Policy(workspace, "analyst", out / "audit.jsonl", read_roots())
    result = await run_session(
        label="analyze", prompt=prompts.ANALYZE_PROMPT, workspace=workspace, policy=policy,
        log_path=out / "events.jsonl", system_append=prompts.ANALYST, tools=["Read", "Glob", "Grep"],
        model=args.model, max_turns=40, max_budget_usd=args.budget, output_schema=prompts.PLAN_SCHEMA,
    )
    append_jsonl(out / "sessions.jsonl", asdict(result) | {"round": 0})
    if result.structured_output is None:
        print(f"분석 실패: {result.subtype}")
        return 1
    (out / "plan.json").write_text(json.dumps(result.structured_output, ensure_ascii=False, indent=2) + "\n",
                                   encoding="utf-8")
    risks = result.structured_output.get("risks", [])
    print(f"plan.json: 위험 {len(risks)}개, {result.num_turns}턴, {result.duration_s}초, ${result.cost_usd:.4f}")
    return 0


def split_agents(model: str) -> dict[str, AgentDefinition]:
    return {
        "implementer": AgentDefinition(
            description="Rust 코드를 쓰고 빌드·테스트한다. rust_app/, reports/, verify/ 에만 쓴다.",
            prompt=prompts.IMPLEMENTER + prompts.IMPLEMENTER_V2_EXTRA, tools=FILE_TOOLS, model="inherit"),
        "verifier": AgentDefinition(
            description="Rust 구현과 Python 기준 구현이 다르게 동작하는 입력을 찾는다. verify/ 에만 쓴다.",
            prompt=prompts.VERIFIER, tools=FILE_TOOLS, model="inherit"),
    }


async def cmd_port(args: argparse.Namespace) -> int:
    out = run_dir(args.run)
    project = args.project.resolve()
    manifest = json.loads((project / "automation" / "port.json").read_text(encoding="utf-8"))
    workspace = prepare_workspace(project, args.run, args.plan.resolve() if args.plan else None)
    split = args.mode == "split"
    v2 = args.policy == "v2"
    main_role = "coordinator" if split else ("implementer_v2" if v2 else "implementer")
    policy = Policy(workspace, main_role, out / "audit.jsonl", read_roots(),
                    role_alias={"implementer": "implementer_v2"} if v2 else {})
    domains = CRATES_DOMAINS if args.allow_crates else []
    sandbox = sandbox_settings(workspace, deny_read_paths(workspace), domains) if v2 else None
    (out / "run.json").write_text(json.dumps({
        "project": manifest["name"], "mode": args.mode, "model": args.model, "max_rounds": args.max_rounds,
        "budget_usd": args.budget, "started": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "plan": bool(args.plan), "policy": args.policy, "allow_crates": args.allow_crates}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    session_id: str | None = None
    spent = 0.0
    previous_failing: list[str] | None = None
    stop_reason = "max_rounds"
    for round_no in range(1, args.max_rounds + 1):
        remaining = args.budget - spent
        if remaining <= 0.05:
            stop_reason = "budget"
            break
        if round_no == 1:
            prompt = prompts.SPLIT_PORT_PROMPT if split else prompts.PORT_PROMPT
        else:
            prompt = prompts.FIX_PROMPT.format(feedback=gate_mod.feedback(gate))
        before = snapshot_rust(workspace)
        result = await run_session(
            label=f"round{round_no}", prompt=prompt, workspace=workspace, policy=policy,
            log_path=out / "events.jsonl",
            system_append=prompts.COORDINATOR if split else prompts.IMPLEMENTER + (prompts.IMPLEMENTER_V2_EXTRA if v2 else ""),
            tools=FILE_TOOLS + (["Agent"] if split else []), model=args.model, max_turns=args.max_turns,
            max_budget_usd=remaining, resume=session_id, agents=split_agents(args.model) if split else None,
            sandbox=sandbox,
        )
        # 이어 실행(resume)한 세션의 비용은 대화 전체 누적값이므로 이번 라운드 비용은 차이로 계산한다
        round_cost = max(result.cost_usd - spent, 0.0) if session_id else result.cost_usd
        spent += round_cost
        session_id = result.session_id or session_id
        changed = snapshot_rust(workspace) != before
        gate = gate_mod.run_gate(workspace, manifest)
        gate_mod.save(gate, out / f"gate_round{round_no}.json")
        append_jsonl(out / "sessions.jsonl", asdict(result) | {
            "round": round_no, "round_cost_usd": round(round_cost, 4), "rust_changed": changed,
            "gate_ok": gate.ok, "gate_failing": gate.failing(), "fuzz_seed": gate.fuzz_seed})
        print(f"round {round_no}: {result.subtype}, {result.num_turns}턴, ${round_cost:.4f}, "
              f"게이트 {'통과' if gate.ok else '실패 ' + ','.join(gate.failing())}")
        if gate.protected_changed:
            stop_reason = "protected_changed"
            break
        if gate.ok:
            stop_reason = "gate_passed"
            break
        if not changed and gate.failing() == previous_failing:
            stop_reason = "no_progress"
            break
        previous_failing = gate.failing()

    # 같은 실행 파일로 게이트를 한 번 더(다른 무작위 입력) — 통과가 우연이 아닌지 본다
    confirm = gate_mod.run_gate(workspace, manifest) if stop_reason == "gate_passed" else None
    if confirm:
        gate_mod.save(confirm, out / "gate_confirm.json")
    summary = {"stop_reason": stop_reason, "rounds": round_no, "cost_usd": round(spent, 4),
               "confirm_gate_ok": confirm.ok if confirm else None}
    (out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    collect_outputs(workspace, out)
    print(json.dumps(summary, ensure_ascii=False))
    return 0 if stop_reason == "gate_passed" else 1


async def cmd_followup(args: argparse.Namespace) -> int:
    """게이트를 통과한 실행에서, 에이전트 보고서의 '확신하지 못하는 부분'을 다음 라운드의 지시로 돌려준다."""
    out = run_dir(args.run)
    workspace = WORK / args.run
    run = json.loads((out / "run.json").read_text(encoding="utf-8"))
    sessions = [json.loads(line) for line in (out / "sessions.jsonl").read_text(encoding="utf-8").split("\n") if line]
    manifest = json.loads((workspace / "automation" / "port.json").read_text(encoding="utf-8"))
    spent = sum(s.get("round_cost_usd", 0.0) for s in sessions)
    previous_total = sessions[-1]["cost_usd"]  # 이어 실행하면 대화 전체 누적값이 오므로 차이를 낸다
    round_no = sessions[-1]["round"] + 1
    v2 = run.get("policy") == "v2"
    policy = Policy(workspace, "implementer_v2" if v2 else "implementer", out / "audit.jsonl", read_roots())
    domains = CRATES_DOMAINS if run.get("allow_crates") else []
    sandbox = sandbox_settings(workspace, deny_read_paths(workspace), domains) if v2 else None
    for name in ("heldout.json", "plan_probes.json"):  # 후속 라운드 전의 평가를 남긴다
        if (out / name).exists():
            shutil.copy2(out / name, out / name.replace(".json", f"_round{round_no - 1}.json"))
    result = await run_session(
        label=f"round{round_no}-followup", prompt=prompts.FOLLOWUP_PROMPT, workspace=workspace, policy=policy,
        log_path=out / "events.jsonl", system_append=prompts.IMPLEMENTER + (prompts.IMPLEMENTER_V2_EXTRA if v2 else ""),
        tools=FILE_TOOLS, model=run["model"], max_turns=args.max_turns,
        max_budget_usd=max(run["budget_usd"] - spent, 0.1), resume=sessions[-1]["session_id"], sandbox=sandbox,
    )
    round_cost = max(result.cost_usd - previous_total, 0.0)
    gate = gate_mod.run_gate(workspace, manifest)
    gate_mod.save(gate, out / f"gate_round{round_no}.json")
    append_jsonl(out / "sessions.jsonl", asdict(result) | {
        "round": round_no, "followup": True, "round_cost_usd": round(round_cost, 4), "rust_changed": True,
        "gate_ok": gate.ok, "gate_failing": gate.failing(), "fuzz_seed": gate.fuzz_seed})
    summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
    summary |= {"rounds": round_no, "cost_usd": round(spent + round_cost, 4), "followup_gate_ok": gate.ok}
    (out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    collect_outputs(workspace, out)
    print(f"round {round_no}(후속): {result.subtype}, {result.num_turns}턴, ${round_cost:.4f}, "
          f"게이트 {'통과' if gate.ok else '실패 ' + ','.join(gate.failing())}")
    return 0 if gate.ok else 1


def snapshot_rust(workspace: Path) -> dict[str, float]:
    root = workspace / "rust_app"
    if not root.exists():
        return {}
    return {str(p.relative_to(root)): p.stat().st_mtime for p in root.rglob("*")
            if p.is_file() and "target" not in p.relative_to(root).parts}


def collect_outputs(workspace: Path, out: Path) -> None:
    """작업 폴더의 산출물(소스·보고서·검증 스크립트)을 기록 폴더로 복사한다."""
    for sub in ("rust_app", "reports", "verify"):
        src = workspace / sub
        dst = out / "workspace" / sub
        if dst.exists():
            shutil.rmtree(dst)
        if not src.exists():
            continue
        try:
            # 검증 역할은 시험용으로 권한 0 파일·순환 링크도 만든다(split1). 링크는 링크로 두고, 못 읽는 파일은 건너뛴다
            shutil.copytree(src, dst, symlinks=True, ignore_dangling_symlinks=True,
                            ignore=shutil.ignore_patterns("target", ".venv", "__pycache__"))
        except shutil.Error as err:
            skipped = [str(Path(e[0]).relative_to(workspace)) for e in err.args[0]]
            (out / "collect_skipped.txt").write_text("\n".join(skipped) + "\n", encoding="utf-8")


def cmd_heldout(args: argparse.Namespace) -> int:
    out = run_dir(args.run)
    manifest = json.loads((WORK / args.run / "automation" / "port.json").read_text(encoding="utf-8"))
    binary = WORK / args.run / "rust_app" / "target" / "release" / manifest["binary"]
    reference = WORK / args.run / manifest["python"]
    hidden = subprocess.run([sys.executable, str(REPO / "ch08" / "heldout" / "evaluate.py"), str(binary),
                             "--reference", str(reference), "--out", str(out / "heldout.json")])
    probes = subprocess.run([sys.executable, str(REPO / "ch08" / "heldout" / "plan_probes.py"), str(binary),
                             "--reference", str(reference), "--project", str(WORK / args.run),
                             "--out", str(out / "plan_probes.json")])
    return hidden.returncode or probes.returncode


def main() -> int:
    parser = argparse.ArgumentParser(description="Python → Rust porting pipeline (ch08)")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("analyze", "port"):
        p = sub.add_parser(name)
        p.add_argument("project", type=Path)
        p.add_argument("--run", required=True)
        p.add_argument("--model", default="opus")
        p.add_argument("--budget", type=float, default=2.0 if name == "analyze" else 10.0)
        if name == "port":
            p.add_argument("--plan", type=Path)
            p.add_argument("--mode", choices=["single", "split"], default="single")
            p.add_argument("--max-rounds", type=int, default=4)
            p.add_argument("--max-turns", type=int, default=120)
            p.add_argument("--allow-crates", action="store_true",
                           help="샌드박스에서 crates.io 접속을 허용(외부 크레이트 사용, 09장)")
            p.add_argument("--policy", choices=["v1", "v2"], default="v2",
                           help="v1: 검증 스크립트 실행 불가(08-3 첫 실행), v2: verify/ 스크립트 실행 + 샌드박스")
    for name in ("heldout", "report"):
        sub.add_parser(name).add_argument("--run", required=True)
    followup = sub.add_parser("followup")
    followup.add_argument("--run", required=True)
    followup.add_argument("--max-turns", type=int, default=80)
    args = parser.parse_args()
    if args.command == "analyze":
        return asyncio.run(cmd_analyze(args))
    if args.command == "port":
        return asyncio.run(cmd_port(args))
    if args.command == "followup":
        return asyncio.run(cmd_followup(args))
    if args.command == "heldout":
        return cmd_heldout(args)
    return write_report(run_dir(args.run), WORK / args.run)


if __name__ == "__main__":
    sys.exit(main())
