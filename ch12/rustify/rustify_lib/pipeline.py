"""이식 파이프라인 (12-2, 12-4): 입력 검사 → 작업 폴더 준비 → (분석) → 생성·수정 라운드 → 후속 확인 → 확인 게이트 → 수집.

멈추는 조건(stop_reason)과 종료 코드:
  gate_passed 0 | input_rejected 2 | protected_changed 3 |
  budget, max_rounds, no_progress, time_limit, agent_error 1
"""

from __future__ import annotations

import difflib
import json
import os
import shutil
import subprocess
import sys
import time
from dataclasses import asdict
from pathlib import Path

from . import gate as gate_mod
from . import prompts
from .engines import SessionResult, make_engine
from .project import HARNESS, check_project, load_manifest
from .repro import env_info, scan_outputs, sha256

ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / "runs"
WORK = Path.home() / "work" / "rustify_ws"
EXIT = {"gate_passed": 0, "input_rejected": 2, "protected_changed": 3}
HUMAN_FILES = ("python_src", "tests", "contracts", "automation")
COPY_IGNORE = shutil.ignore_patterns(".venv", "__pycache__", ".pytest_cache", ".hypothesis", "rust_app", "reports",
                                     "verify", "port", "target", ".rustify", ".cargo-home")


def read_roots() -> list[Path]:
    roots = [Path(sys.base_prefix) / "lib" / f"python{sys.version_info.major}.{sys.version_info.minor}"]
    roots += sorted((Path.home() / ".rustup" / "toolchains").glob("*/lib/rustlib/src"))
    return [r.resolve() for r in roots if r.exists()]


def deny_read(workspace: Path) -> list[Path]:
    """셸 명령이 읽지 못하게 할 곳: 인증 정보, 다른 실행의 작업 폴더, 예제 저장소(이전 장의 Rust 구현)."""
    home = Path.home()
    paths = [home / ".ssh", home / ".claude", home / ".claude.json", home / ".codex", home / "work" / "rust-tutorial"]
    paths += [p for p in WORK.iterdir() if p.is_dir() and p != workspace]
    return [p for p in paths if p.exists()]


def append_jsonl(path: Path, row: dict) -> None:
    with path.open("a", encoding="utf-8") as fp:
        fp.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")


def write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")


def prepare(project: Path, workspace: Path, previous: Path | None) -> str:
    """작업 폴더를 새로 만들고 하네스를 넣는다. 하네스의 해시를 돌려준다(게이트가 바뀌었는지 확인)."""
    if workspace.exists():
        shutil.rmtree(workspace)
    shutil.copytree(project, workspace, ignore=COPY_IGNORE)
    shutil.copytree(HARNESS, workspace / ".rustify", ignore=shutil.ignore_patterns("__pycache__"))
    for sub in ("reports", "verify"):
        (workspace / sub).mkdir()
    if previous:  # 증분 이식: 이전 실행의 Rust 구현과 보고서에서 시작한다
        shutil.copytree(previous / "rust_app", workspace / "rust_app", ignore=shutil.ignore_patterns("target"))
        # 이전 실행의 검증 스크립트도 가져온다(처음 판은 빠뜨려 mdtoc_s2 의 에이전트가 다시 만들었다. 12-6)
        for sub in ("reports", "verify"):
            if (previous / sub).exists():
                shutil.copytree(previous / sub, workspace / sub, dirs_exist_ok=True,
                                ignore=shutil.ignore_patterns("__pycache__", "data", "*.bin"))
    env = {k: v for k, v in os.environ.items() if k != "VIRTUAL_ENV"}  # 도구 자신의 가상 환경을 넘기지 않는다
    subprocess.run(["uv", "sync", "-q"], cwd=workspace, check=True, env=env)
    return gate_mod.harness_digest(workspace)


def human_changes(old: Path, new: Path, limit: int = 400) -> str:
    """이전 실행의 사람 파일과 지금 파일의 차이(unified diff). 에이전트에게 '무엇이 바뀌었나'로 준다."""
    lines: list[str] = []
    for name in HUMAN_FILES:
        old_files = {p.relative_to(old).as_posix() for p in (old / name).rglob("*") if p.is_file()} if (old / name).exists() else set()
        new_files = {p.relative_to(new).as_posix() for p in (new / name).rglob("*") if p.is_file()} if (new / name).exists() else set()
        for rel in sorted(old_files | new_files):
            if "__pycache__" in rel:
                continue
            a = (old / rel).read_bytes() if rel in old_files else b""
            b = (new / rel).read_bytes() if rel in new_files else b""
            if a == b:
                continue
            try:
                diff = difflib.unified_diff(a.decode().splitlines(), b.decode().splitlines(), f"before/{rel}",
                                            f"after/{rel}", lineterm="", n=2)
                lines += list(diff)
            except UnicodeDecodeError:
                lines.append(f"(바이너리 파일 바뀜: {rel})")
    if len(lines) > limit:
        lines = lines[:limit] + [f"... ({len(lines) - limit}줄 생략. 파일을 직접 읽으세요)"]
    return "\n".join(lines) or "(사람 파일의 차이 없음)"


def snapshot_rust(workspace: Path) -> dict[str, float]:
    root = workspace / "rust_app"
    if not root.exists():
        return {}
    return {str(p.relative_to(root)): p.stat().st_mtime for p in root.rglob("*")
            if p.is_file() and "target" not in p.relative_to(root).parts}


def collect(workspace: Path, out: Path, binary: str) -> dict:
    """산출물을 기록 폴더로 옮기고 비밀 검사를 한다. 실행 파일은 해시만 남긴다."""
    dst = out / "workspace"
    if dst.exists():
        shutil.rmtree(dst)
    for sub in ("rust_app", "reports", "verify"):
        src = workspace / sub
        if src.exists():
            shutil.copytree(src, dst / sub, symlinks=True, ignore_dangling_symlinks=True,
                            ignore=shutil.ignore_patterns("target", "__pycache__", "*.bin", "data"))
    big = [p for p in dst.rglob("*") if p.is_file() and p.stat().st_size > 1_000_000]
    for path in big:  # 에이전트가 만든 큰 검증 데이터는 기록하지 않는다
        path.unlink()
    exe = workspace / "rust_app" / "target" / "release" / binary
    return {"binary_sha256": sha256(exe), "binary_bytes": exe.stat().st_size if exe.exists() else None,
            "cargo_lock_sha256": sha256(workspace / "rust_app" / "Cargo.lock"),
            "dropped_large_files": [p.relative_to(dst).as_posix() for p in big],
            "secret_scan": scan_outputs(dst)}


async def run_pipeline(args) -> int:
    project = args.project.resolve()
    out = RUNS / args.run
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    started = time.monotonic()
    summary: dict = {"run": args.run, "engine": args.engine, "stop_reason": None, "rounds": 0, "cost_usd": 0.0,
                     "tokens": {}, "human_interventions": 0}

    def finish(reason: str) -> int:
        summary["stop_reason"] = reason
        summary["wall_s"] = round(time.monotonic() - started, 1)
        write_json(out / "summary.json", summary)
        print(json.dumps({k: summary[k] for k in ("stop_reason", "rounds", "cost_usd", "wall_s")}, ensure_ascii=False))
        return EXIT.get(reason, 1)

    # 1. 입력 검사(12-1). 통과하지 못하면 에이전트를 부르지 않는다
    report = check_project(project)
    (out / "check.txt").write_text(report.render() + "\n", encoding="utf-8")
    if not report.ok:
        print(report.render())
        return finish("input_rejected")

    # 2. 작업 폴더
    manifest = load_manifest(project)
    workspace = WORK / args.run
    WORK.mkdir(parents=True, exist_ok=True)
    # --from: rustify 실행 이름, 또는 다른 도구가 만든 작업 폴더 경로(예: 8장 porter 의 ~/work/ch08_ws/single2)
    previous = (Path(args.base).expanduser().resolve() if "/" in args.base else WORK / args.base) if args.base else None
    if previous and not (previous / "rust_app").exists():
        raise SystemExit(f"--from 실행의 작업 폴더가 없습니다: {previous}")
    changes = human_changes(previous, project) if previous else None
    harness_sha = prepare(project, workspace, previous)
    if args.plan:
        (workspace / "port").mkdir(exist_ok=True)
        shutil.copy2(args.plan, workspace / "port" / "plan.json")
    engine = make_engine(args.engine, args.model)
    write_json(out / "run.json", {
        "project": manifest["name"], "project_path": str(project.relative_to(ROOT.parents[1])) if project.is_relative_to(ROOT.parents[1]) else project.name,
        "baseline_sha256": sha256(project / "baseline.lock"), "harness_sha256": harness_sha,
        "engine": args.engine, "model": args.model, "from": args.base, "plan": bool(args.plan),
        "analyze": args.analyze, "followup": args.followup, "allow_crates": args.allow_crates,
        "budget_usd": args.budget, "max_rounds": args.max_rounds, "max_minutes": args.max_minutes,
        "started": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "env": env_info(workspace)})
    if changes is not None:
        (out / "changes.diff").write_text(changes + "\n", encoding="utf-8")

    common = dict(workspace=workspace, log_path=out / "events.jsonl", audit_path=out / "audit.jsonl",
                  read_roots=read_roots(), deny_read=deny_read(workspace), allow_crates=args.allow_crates)
    spent = 0.0
    session_total = 0.0  # 이어 실행 중인 세션의 지금까지 누적 비용

    def account(result: SessionResult, resumed: bool, label: str, gate: gate_mod.GateResult | None,
                changed: bool | None) -> float:
        nonlocal spent, session_total
        cost = None
        if result.cost_usd is not None:
            # 이어 실행한 Claude 세션의 비용은 대화 전체 누적값이라 같은 세션의 직전 누적값을 뺀다.
            # (처음 판은 분석 세션 비용까지 포함한 spent 를 빼서 후속 라운드를 0으로 기록했다. 12-2)
            cost = max(result.cost_usd - session_total, 0.0) if resumed else result.cost_usd
            if label != "analyze":
                session_total = result.cost_usd
            spent += cost
            summary["cost_usd"] = round(spent, 4)
        for key, value in result.tokens.items():
            summary["tokens"][key] = summary["tokens"].get(key, 0) + value
        append_jsonl(out / "sessions.jsonl", asdict(result) | {
            "stage": label, "round_cost_usd": None if cost is None else round(cost, 4), "rust_changed": changed,
            "gate_ok": gate.ok if gate else None, "gate_failing": gate.failing() if gate else None,
            "fuzz_seed": gate.fuzz_seed if gate else None})
        return cost or 0.0

    def over_time() -> bool:
        return args.max_minutes is not None and time.monotonic() - started > args.max_minutes * 60

    # 3. 분석(선택, Claude 엔진만: 구조화 출력이 필요)
    if args.analyze and not args.plan and args.engine == "claude":
        result = await engine.session(label="analyze", prompt=prompts.ANALYZE_PROMPT, system=prompts.ANALYST,
                                      role="analyst", budget_usd=min(2.0, args.budget), max_turns=40,
                                      output_schema=prompts.PLAN_SCHEMA, **common)
        account(result, False, "analyze", None, None)
        if result.structured_output:
            (workspace / "port").mkdir(exist_ok=True)
            write_json(workspace / "port" / "plan.json", result.structured_output)
            write_json(out / "plan.json", result.structured_output)

    # 4. 생성·수정 라운드
    system = prompts.implementer(manifest["binary"], args.allow_crates)
    session_id = None
    gate = None
    previous_failing = None
    reason = "max_rounds"
    followup_done = not args.followup
    round_no = 0
    while round_no < args.max_rounds:
        if args.engine == "claude" and args.budget - spent <= 0.05:
            reason = "budget"
            break
        if over_time():
            reason = "time_limit"
            break
        round_no += 1
        if gate is None:
            prompt = prompts.UPDATE_PROMPT.format(changes=changes) if previous else prompts.PORT_PROMPT
            label = "update" if previous else "port"
        elif gate.ok:
            prompt, label, followup_done = prompts.FOLLOWUP_PROMPT, "followup", True
        else:
            prompt, label = prompts.FIX_PROMPT.format(feedback=gate_mod.feedback(gate)), "fix"
        before = snapshot_rust(workspace)
        result = await engine.session(label=f"round{round_no}-{label}", prompt=prompt, system=system,
                                      role="implementer", budget_usd=max(args.budget - spent, 0.1),
                                      max_turns=args.max_turns, resume=session_id, **common)
        resumed = session_id is not None
        session_id = result.session_id or session_id
        changed = snapshot_rust(workspace) != before
        gate = gate_mod.run_gate(workspace, manifest, harness_sha, sandbox=not args.no_gate_sandbox)
        gate_mod.save(gate, out / f"gate_round{round_no}.json")
        cost = account(result, resumed, label, gate, changed)
        summary["rounds"] = round_no
        print(f"round {round_no} ({label}): {result.status}, {result.num_turns}턴, "
              f"{'$' + format(cost, '.4f') if result.cost_usd is not None else '-'}, "
              f"게이트 {'통과' if gate.ok else '실패 ' + ','.join(gate.failing())}", flush=True)
        if gate.protected_changed:
            reason = "protected_changed"
            break
        if result.status and result.status.startswith("exception") and not changed:
            reason = "agent_error"
            break
        if gate.ok and followup_done:
            reason = "gate_passed"
            break
        if not gate.ok and not changed and gate.failing() == previous_failing:
            reason = "no_progress"
            break
        previous_failing = None if gate.ok else gate.failing()
    if gate is not None and gate.ok and reason == "max_rounds":
        reason = "gate_passed"  # 후속 확인을 못 했지만 게이트는 통과한 상태로 끝남
        summary["followup_skipped"] = not followup_done

    # 5. 확인 게이트: 같은 실행 파일, 다른 시드
    if reason == "gate_passed":
        confirm = gate_mod.run_gate(workspace, manifest, harness_sha, sandbox=not args.no_gate_sandbox)
        gate_mod.save(confirm, out / "gate_confirm.json")
        summary["confirm_gate_ok"] = confirm.ok
        if not confirm.ok:
            reason = "confirm_failed"
    summary["gate_sandboxed"] = gate.sandboxed if gate else None
    # 게이트를 통과해도 마지막 세션이 상한(예산·턴)으로 끊겼으면 에이전트는 일을 끝내지 못한 것이다.
    # fail_budget 실행에서 게이트는 통과했지만 노트에는 "미완료, 코드 포인트 비교 실패"가 적혀 있었다(12-6)
    if session_id is not None and result.status and result.status != "success":
        summary["warnings"] = [f"마지막 세션이 끝나지 않음({result.status}). 게이트 밖의 검증이 남았을 수 있음"]
    summary["artifacts"] = collect(workspace, out, manifest["binary"])
    return finish(reason)


async def replay(args) -> int:
    """기록만으로 검증을 다시 한다: 깨끗한 폴더 + 기록된 Rust 소스 + 지금의 프로젝트(승인본이 같아야 함)."""
    out = RUNS / args.run
    run = json.loads((out / "run.json").read_text(encoding="utf-8"))
    summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
    project = (ROOT.parents[1] / run["project_path"]).resolve()
    if sha256(project / "baseline.lock") != run["baseline_sha256"]:
        print("프로젝트의 승인본(baseline.lock)이 실행 때와 다릅니다. 같은 입력으로 재현할 수 없습니다", file=sys.stderr)
        return 2
    workspace = WORK / f"{args.run}-replay"
    harness_sha = prepare(project, workspace, None)
    if harness_sha != run["harness_sha256"]:
        print("주의: 하네스(.rustify)가 실행 때와 다릅니다", file=sys.stderr)
    shutil.copytree(out / "workspace" / "rust_app", workspace / "rust_app")
    manifest = load_manifest(project)
    seeds = [json.loads(p.read_text(encoding="utf-8"))["fuzz_seed"]
             for p in [out / "gate_confirm.json"] if p.exists()]
    results = []
    for seed in seeds or [None]:
        g = gate_mod.run_gate(workspace, manifest, harness_sha, seed=seed, sandbox=not args.no_gate_sandbox)
        results.append({"seed": g.fuzz_seed, "ok": g.ok, "failing": g.failing()})
    exe = workspace / "rust_app" / "target" / "release" / manifest["binary"]
    original = summary.get("artifacts", {}).get("binary_sha256")
    data = {"gates": results, "binary_sha256": sha256(exe), "original_binary_sha256": original,
            "same_binary": sha256(exe) == original, "env": env_info(workspace)}
    write_json(out / "replay.json", data)
    print(json.dumps({"gates": results, "same_binary": data["same_binary"]}, ensure_ascii=False))
    return 0 if all(r["ok"] for r in results) else 1
