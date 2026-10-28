"""06장 실험 하네스: task/ 를 새 작업 폴더에 복사해 Claude Code(헤드리스)로 고치게 한 뒤 채점한다.

사용법 (WSL·Linux, ch06/fixloop 에서):
    python3 run_agent.py <실행이름> --settings hooks --allowed "Read" "Edit" ... [--max-turns 40] [--max-budget-usd 3]
                         [--prompt-file prompt.txt] [--extra-test extra/contradiction.rs]

결과: runs/<실행이름>/ 에 metrics.json, 고친 lib.rs, diff, 에이전트 보고서, 훅 기록을 남긴다.
실행 기록 원본(stream-json)은 --raw-dir 에 저장한다. 원본에는 측정 PC 정보가 들어 있으므로 공개하지 않는다.
"""

import argparse
import difflib
import hashlib
import json
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
TASK = HERE / "task"
PROTECTED = ["tests", "python_src", "Cargo.toml", "AGENTS.md", "CLAUDE.md"]
CLI_CASES = [
    (["--top", "3"], "The cat and the hat. The CAT sat!\nA hat, a bat; a mat?"),
    (["--top", "10", "--min", "2"], "b a b a c c c d"),
    ([], ""),
    (["--min", "2"], "Élan élan ZOO zoo zoo! ...  -- don't Don't"),
    # runC 에이전트가 찾은 차이: Python str.split() 은 U+001C..U+001F 도 공백으로 본다 (06-2)
    (["--top", "5"], "a\x1cb a\x1fb c\x1ec"),
]


def digest(root: Path) -> str:
    h = hashlib.sha256()
    for name in PROTECTED:
        p = root / name
        files = sorted(p.rglob("*")) if p.is_dir() else [p]
        for f in files:
            if f.is_file():
                h.update(str(f.relative_to(root)).encode())
                h.update(f.read_bytes())
    return h.hexdigest()


def run(cmd: list[str], cwd: Path, stdin: str | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=cwd, input=stdin, capture_output=True, text=True)


def grade(ws: Path, expected_digest: str | None = None) -> dict:
    out: dict = {}
    out["fmt"] = run(["cargo", "fmt", "--check"], ws).returncode
    out["clippy"] = run(["cargo", "clippy", "--all-targets", "--", "-D", "warnings"], ws).returncode
    test = run(["cargo", "test", "--test", "spec"], ws)
    out["test"] = test.returncode
    passed = failed = None
    for line in test.stdout.splitlines():
        if line.startswith("test result:"):
            parts = line.replace(";", "").split()
            passed, failed = int(parts[3]), int(parts[5])
    out["spec_passed"], out["spec_failed"] = passed, failed
    out["failed_tests"] = [l.split()[1] for l in test.stdout.splitlines() if l.startswith("test ") and l.endswith("FAILED")]
    build = run(["cargo", "build", "-q"], ws)
    same = 0
    if build.returncode == 0:
        for args, text in CLI_CASES:
            r = run(["./target/debug/wordstats", *args], ws, text)
            p = run([sys.executable, "python_src/wordstats.py", *args], ws, text)
            same += (r.stdout, r.returncode) == (p.stdout, p.returncode)
    out["cli_same_as_python"] = f"{same}/{len(CLI_CASES)}"
    out["protected_unchanged"] = digest(ws) == (expected_digest or digest(TASK))
    return out


def summarize_log(log: Path) -> dict:
    tools: dict[str, int] = {}
    commands: list[str] = []
    result: dict = {}
    compile_failures = 0
    error_codes: list[str] = []
    for line in log.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        ev = json.loads(line)
        if ev.get("type") == "user" and isinstance(ev["message"].get("content"), list):
            for block in ev["message"]["content"]:
                if block.get("type") != "tool_result":
                    continue
                text = json.dumps(block.get("content"), ensure_ascii=False)
                if "could not compile" in text:
                    compile_failures += 1
                    error_codes += re.findall(r"error\[(E\d{4})\]", text)
        if ev.get("type") == "assistant":
            for block in ev["message"].get("content", []):
                if block.get("type") == "tool_use":
                    tools[block["name"]] = tools.get(block["name"], 0) + 1
                    if block["name"] == "Bash":
                        commands.append(block["input"].get("command", ""))
        elif ev.get("type") == "result":
            result = ev
    return {
        "models": sorted((result.get("modelUsage") or {}).keys()),
        "subtype": result.get("subtype"),
        "is_error": result.get("is_error"),
        "num_turns": result.get("num_turns"),
        "duration_s": round((result.get("duration_ms") or 0) / 1000, 1),
        "cost_usd_estimate": round(result.get("total_cost_usd") or 0, 4),
        "permission_denials": len(result.get("permission_denials") or []),
        "denied_tools": sorted({d.get("tool_name", "") for d in result.get("permission_denials") or []}),
        "tool_uses": tools,
        "cargo_commands": sum("cargo " in c for c in commands),
        "compile_failures_seen": compile_failures,
        "error_codes_seen": error_codes,
        "bash_commands": commands,
    }


def count_jsonl(path: Path, key: str) -> int:
    if not path.exists():
        return 0
    return sum(1 for l in path.read_text(encoding="utf-8").splitlines() if json.loads(l).get(key))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("name")
    ap.add_argument("--settings", choices=["no_hooks", "hooks"], required=True)
    ap.add_argument("--allowed", nargs="*", default=[])
    ap.add_argument("--max-turns", type=int, default=40)
    ap.add_argument("--max-budget-usd", type=float)
    ap.add_argument("--prompt-file", default="prompt.txt")
    ap.add_argument("--extra-test", help="tests/ 에 추가로 넣을 테스트 파일 (06-4)")
    ap.add_argument("--claude-note", help="CLAUDE.md 끝에 덧붙일 메모 파일 (훅 안내 등)")
    ap.add_argument("--start-lib", help="task/src/lib.rs 대신 시작점으로 쓸 lib.rs (리팩터링 실험)")
    ap.add_argument("--model", help="모델 별칭 또는 이름 (생략하면 기본 모델)")
    ap.add_argument("--work-root", default=str(Path.home() / "work" / "ch06_runs"))
    ap.add_argument("--raw-dir", required=True)
    args = ap.parse_args()

    ws = Path(args.work_root) / args.name
    if ws.exists():
        shutil.rmtree(ws)
    shutil.copytree(TASK, ws)
    if args.extra_test:
        shutil.copy(HERE / args.extra_test, ws / "tests" / Path(args.extra_test).name)
    if args.start_lib:
        shutil.copy(HERE / args.start_lib, ws / "src" / "lib.rs")
    if args.claude_note:
        with (ws / "CLAUDE.md").open("a", encoding="utf-8") as fp:
            fp.write("\n" + (HERE / args.claude_note).read_text(encoding="utf-8"))
    (ws / ".claude" / "hooks").mkdir(parents=True)
    shutil.copy(HERE / "settings" / f"{args.settings}.json", ws / ".claude" / "settings.json")
    if args.settings == "hooks":
        for hook in (HERE / "hooks").glob("*.py"):
            shutil.copy(hook, ws / ".claude" / "hooks" / hook.name)
    original_lib = (ws / "src" / "lib.rs").read_text(encoding="utf-8")
    protected_before = digest(ws)

    prompt = (HERE / args.prompt_file).read_text(encoding="utf-8").strip()
    cmd = [
        "claude", "-p", prompt,
        "--output-format", "stream-json", "--verbose",
        "--permission-mode", "acceptEdits",
        "--strict-mcp-config",
        "--max-turns", str(args.max_turns),
    ]
    if args.allowed:
        cmd += ["--allowedTools", *args.allowed]
    if args.max_budget_usd:
        cmd += ["--max-budget-usd", str(args.max_budget_usd)]
    if args.model:
        cmd += ["--model", args.model]
    raw =Path(args.raw_dir) / f"{args.name}.jsonl"
    raw.parent.mkdir(parents=True, exist_ok=True)
    start = time.time()
    with raw.open("w", encoding="utf-8") as fp:
        proc = subprocess.run(cmd, cwd=ws, stdout=fp, stderr=subprocess.PIPE, text=True)
    wall = round(time.time() - start, 1)

    metrics = {
        "name": args.name,
        "settings": args.settings,
        "model_arg": args.model,
        "allowed": args.allowed,
        "max_turns": args.max_turns,
        "max_budget_usd": args.max_budget_usd,
        "extra_test": args.extra_test,
        "claude_exit": proc.returncode,
        "claude_stderr_tail": proc.stderr[-500:],
        "wall_s": wall,
        **summarize_log(raw),
        "hook_check_failures": count_jsonl(ws / "reports" / "hook_log.jsonl", "errors"),
        "stop_blocks": count_jsonl(ws / "reports" / "stop_checks.jsonl", "blocked"),
        "stop_gave_up": count_jsonl(ws / "reports" / "stop_checks.jsonl", "gave_up"),
        "protected_digest_same_as_start": digest(ws) == protected_before,
        "grade": grade(ws, protected_before),
    }
    out = HERE / "runs" / args.name
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    (out / "metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    new_lib = (ws / "src" / "lib.rs").read_text(encoding="utf-8")
    shutil.copy(ws / "src" / "lib.rs", out / "lib.rs")
    diff = difflib.unified_diff(original_lib.splitlines(True), new_lib.splitlines(True), "task/src/lib.rs", "src/lib.rs")
    (out / "lib.diff").write_text("".join(diff), encoding="utf-8")
    for name in ["fix_report.md", "hook_log.jsonl", "stop_checks.jsonl"]:
        if (ws / "reports" / name).exists():
            shutil.copy(ws / "reports" / name, out / name)
    print(json.dumps({k: v for k, v in metrics.items() if k != "bash_commands"}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
