"""06-4 바깥 재시도 루프: 에이전트 실행 → 검사 → 실패하면 실패 내용을 붙여 다시 실행.

종료 조건 (먼저 걸리는 것):
  1. 성공: fmt·clippy·test 모두 통과
  2. 진전 없음: 실패 서명(실패한 검사 + 실패한 테스트 이름)이 직전 시도와 같다
  3. 시도 횟수 상한 (--attempts)
  4. 누적 비용 상한 (--budget-usd, Claude Code 추정 비용 기준)

사용법 (WSL·Linux, ch06/fixloop 에서):
    python3 retry_loop.py <실행이름> --extra-test extra/contradiction.rs --raw-dir <원본 기록 폴더>
"""

import argparse
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

import run_agent

HERE = Path(__file__).resolve().parent


def checks(ws: Path) -> tuple[bool, dict, str]:
    """검사 결과, 실패 서명, 다음 시도에 넘길 실패 요약."""
    results: dict[str, int] = {}
    details: list[str] = []
    failed_tests: list[str] = []
    for name, cmd in [
        ("fmt", ["cargo", "fmt", "--check"]),
        ("clippy", ["cargo", "clippy", "--all-targets", "--", "-D", "warnings"]),
        ("test", ["cargo", "test"]),
    ]:
        proc = run_agent.run(cmd, ws)
        results[name] = proc.returncode
        if proc.returncode != 0:
            details.append(f"[{name}] 종료 코드 {proc.returncode}\n{(proc.stdout + proc.stderr)[-1200:]}")
            if name == "test":
                failed_tests = sorted(
                    l.split()[1] for l in proc.stdout.splitlines() if l.startswith("test ") and l.endswith("FAILED")
                )
    ok = all(code == 0 for code in results.values())
    signature = {"failed_checks": sorted(k for k, v in results.items() if v), "failed_tests": failed_tests}
    return ok, signature, "\n\n".join(details)


def stop_reason_for(ok: bool, signature: dict, previous: dict | None, spent: float, budget: float) -> str | None:
    """멈출 이유. 계속하면 None. (실험 뒤 main 안의 같은 조건문을 함수로 떼어 냈다. 동작은 같다)"""
    if ok:
        return "success"
    if signature == previous:
        return "no_progress"
    if spent >= budget:
        return "budget"
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("name")
    ap.add_argument("--attempts", type=int, default=3)
    ap.add_argument("--budget-usd", type=float, default=4.0)
    ap.add_argument("--max-turns", type=int, default=30)
    ap.add_argument("--extra-test")
    ap.add_argument("--work-root", default=str(Path.home() / "work" / "ch06_runs"))
    ap.add_argument("--raw-dir", required=True)
    args = ap.parse_args()

    ws = Path(args.work_root) / args.name
    if ws.exists():
        shutil.rmtree(ws)
    shutil.copytree(run_agent.TASK, ws)
    if args.extra_test:
        shutil.copy(HERE / args.extra_test, ws / "tests" / Path(args.extra_test).name)
    (ws / ".claude").mkdir()
    shutil.copy(HERE / "settings" / "no_hooks.json", ws / ".claude" / "settings.json")
    protected = run_agent.digest(ws)

    prompt = (HERE / "prompt.txt").read_text(encoding="utf-8").strip()
    spent = 0.0
    previous: dict | None = None
    attempts: list[dict] = []
    stop_reason = "attempts"
    for i in range(1, args.attempts + 1):
        remaining = round(args.budget_usd - spent, 2)
        cmd = [
            "claude", "-p", prompt,
            "--output-format", "stream-json", "--verbose",
            "--permission-mode", "acceptEdits", "--strict-mcp-config",
            "--allowedTools", "Bash(cargo *)",
            "--max-turns", str(args.max_turns),
            "--max-budget-usd", str(remaining),
        ]
        raw = Path(args.raw_dir) / f"{args.name}_try{i}.jsonl"
        raw.parent.mkdir(parents=True, exist_ok=True)
        start = time.time()
        with raw.open("w", encoding="utf-8") as fp:
            proc = subprocess.run(cmd, cwd=ws, stdout=fp, stderr=subprocess.PIPE, text=True)
        log = run_agent.summarize_log(raw)
        spent += log["cost_usd_estimate"]
        ok, signature, details = checks(ws)
        attempt = {
            "attempt": i,
            "claude_exit": proc.returncode,
            "wall_s": round(time.time() - start, 1),
            **{k: log[k] for k in ("subtype", "num_turns", "duration_s", "cost_usd_estimate", "permission_denials")},
            "checks_ok": ok,
            "signature": signature,
        }
        attempts.append(attempt)
        print(json.dumps(attempt, ensure_ascii=False))
        reason = stop_reason_for(ok, signature, previous, spent, args.budget_usd)
        if reason:
            stop_reason = reason
            break
        previous = signature
        prompt = (
            "이전 시도 후에도 검사가 실패했습니다. 아래 결과를 보고 다시 고쳐 주세요. "
            "고칠 수 없다고 판단되면 그 이유를 reports/fix_report.md 에 적고 끝내세요.\n\n" + details
        )

    summary = {
        "name": args.name,
        "extra_test": args.extra_test,
        "stop_reason": stop_reason,
        "attempts": attempts,
        "total_cost_usd_estimate": round(spent, 4),
        "protected_unchanged": run_agent.digest(ws) == protected,
    }
    out = HERE / "runs" / args.name
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    (out / "loop.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    shutil.copy(ws / "src" / "lib.rs", out / "lib.rs")
    if (ws / "reports" / "fix_report.md").exists():
        shutil.copy(ws / "reports" / "fix_report.md", out / "fix_report.md")
    print(json.dumps({k: v for k, v in summary.items() if k != "attempts"}, ensure_ascii=False))
    return 0 if stop_reason == "success" else 1


if __name__ == "__main__":
    sys.exit(main())
