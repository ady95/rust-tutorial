"""최종 보고서와 산출물 (08-6). 수치는 모두 파이프라인의 기록에서 계산하고, 에이전트가 쓴 글은 따로 표시한다."""

from __future__ import annotations

import hashlib
import json
import platform
import shutil
import subprocess
from collections import Counter
from pathlib import Path


def _jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    # splitlines() 는 JSON 문자열 안의 U+2028·U+0085 에서도 줄을 나누므로 "\n" 으로만 나눈다
    return [json.loads(line) for line in path.read_text(encoding="utf-8").split("\n") if line.strip()]


def _json(path: Path) -> dict | list | None:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def _version(cmd: list[str]) -> str:
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=30).stdout.strip().splitlines()[0]
    except (OSError, IndexError, subprocess.TimeoutExpired):
        return "unknown"


def _sdk_version() -> str:
    try:
        import claude_agent_sdk

        return claude_agent_sdk.__version__
    except (ImportError, AttributeError):
        return "unknown"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def uncertain_section(notes: str) -> list[str]:
    """에이전트 노트에서 '확신하지 못하는 부분' 절(## 3 …)만 꺼낸다. 형식이 다르면 빈 목록."""
    lines, inside = [], False
    for line in notes.split("\n"):
        if line.startswith("## "):
            inside = line.startswith("## 3") or "확신" in line
            continue
        if inside:
            lines.append(line)
    return [line for line in lines if line.strip()]


def write_report(out: Path, workspace: Path) -> int:
    run = _json(out / "run.json") or {}
    summary = _json(out / "summary.json") or {}
    sessions = _jsonl(out / "sessions.jsonl")
    audit = _jsonl(out / "audit.jsonl")
    heldout = _json(out / "heldout.json")
    manifest = _json(workspace / "automation" / "port.json") or {}

    artifacts = out / "artifacts"
    artifacts.mkdir(exist_ok=True)
    binary = workspace / "rust_app" / "target" / "release" / manifest.get("binary", "")
    binary_line = "없음"
    if binary.is_file():
        shutil.copy2(binary, artifacts / binary.name)
        binary_line = f"`artifacts/{binary.name}` sha256 `{_sha256(binary)[:16]}…`"
    for name in ("Cargo.toml", "Cargo.lock"):
        if (workspace / "rust_app" / name).exists():
            shutil.copy2(workspace / "rust_app" / name, artifacts / name)

    versions = {
        "claude_code": next((s.get("claude_code_version") for s in sessions if s.get("claude_code_version")), None),
        "model": next((s.get("model") for s in sessions if s.get("model")), None),
        "rustc": _version(["rustc", "--version"]),
        "cargo": _version(["cargo", "--version"]),
        "python": _version(["python3", "--version"]),
        "os": f"{platform.system()} {platform.release()}",
        "claude_agent_sdk": _sdk_version(),
    }
    inputs = {name: _sha256(workspace / name)[:16] for name in ("baseline.lock", "port/plan.json")
              if (workspace / name).exists()}
    rust_files = sorted((workspace / "rust_app").rglob("*.rs")) if (workspace / "rust_app").exists() else []
    rust_files = [p for p in rust_files if "target" not in p.parts]
    loc = {str(p.relative_to(workspace)): sum(1 for _ in p.open(encoding="utf-8")) for p in rust_files}

    lines = [f"# 이식 보고서: {run.get('project', '?')} ({out.name})", ""]
    lines += ["이 보고서의 수치는 파이프라인 기록(sessions.jsonl, gate_*.json, audit.jsonl, heldout.json)에서 계산했다.",
              "에이전트가 쓴 글은 마지막 절에 따로 붙였다.", "", "## 결과", ""]
    lines += ["| 항목 | 값 |", "|---|---|",
              f"| 모드 | {run.get('mode')} (계획 사용: {run.get('plan')}) |",
              f"| 종료 이유 | {summary.get('stop_reason')} |",
              f"| 라운드 | {summary.get('rounds')} / 최대 {run.get('max_rounds')} |",
              f"| 확인 게이트(다른 무작위 입력) | {summary.get('confirm_gate_ok')} |",
              f"| 추정 비용 | ${summary.get('cost_usd', 0):.4f} (상한 ${run.get('budget_usd')}) |",
              f"| 실행 파일 | {binary_line} |",
              f"| Rust 코드 | {len(loc)}개 파일 {sum(loc.values())}줄 |", ""]
    if heldout:
        same = sum(r["same"] for r in heldout)
        lines += [f"숨긴 평가: {same}/{len(heldout)} 일치", ""]
        lines += ["| 입력 | 결과 | 다른 코드 포인트 수 |", "|---|---|---|"]
        lines += [f"| {r['input']} | {'같음' if r['same'] else '다름'} | {r.get('differing_codepoints', '-')} |" for r in heldout]
        lines.append("")
    probes = _json(out / "plan_probes.json")
    if probes:
        same = sum(r["same"] for r in probes)
        lines += [f"계획의 위험 점검 입력: {same}/{len(probes)} 일치"]
        lines += [f"- 다름: {r['probe']} (python {r['python_exit']}, rust {r['rust_exit']})" for r in probes if not r["same"]]
        lines.append("")

    notes_path = workspace / "reports" / "port_notes.md"
    notes = notes_path.read_text(encoding="utf-8") if notes_path.exists() else ""
    uncertain = uncertain_section(notes)
    lines += ["## 미검증 항목과 사람이 정할 일", "",
              "에이전트 노트의 '확신하지 못하는 부분'을 그대로 옮겼다. 게이트와 숨긴 평가는 이 항목을 시험하지 않는다.", ""]
    lines += uncertain or ["(노트에서 해당 절을 찾지 못함 — 노트 전체를 사람이 읽어야 한다)"]
    lines.append("")

    lines += ["## 라운드별 기록", "", "| 라운드 | 결과 | 턴 | 시간(초) | 비용 | 코드 변경 | 게이트 실패 단계 | fuzz seed |",
              "|---|---|---|---|---|---|---|---|"]
    for s in sessions:
        lines.append(f"| {s.get('round')} | {s.get('subtype')} | {s.get('num_turns')} | {s.get('duration_s')} | "
                     f"${s.get('round_cost_usd', s.get('cost_usd', 0)):.4f} | {s.get('rust_changed', '-')} | "
                     f"{', '.join(s.get('gate_failing') or []) or '없음'} | {s.get('fuzz_seed', '-')} |")
    lines.append("")

    tools = Counter()
    subagents = Counter()
    for s in sessions:
        tools.update(s.get("tool_calls") or {})
        subagents.update(s.get("subagent_calls") or {})
    by_role = Counter((a["role"], a["decision"]) for a in audit)
    lines += ["## 도구 호출과 권한", "",
              "도구 호출(메인 에이전트): " + ", ".join(f"{k} {v}" for k, v in tools.most_common()),
              ""]
    if subagents:
        lines += ["서브에이전트 호출: " + ", ".join(f"{k} {v}" for k, v in subagents.most_common()), ""]
    lines += ["| 역할 | 허용 | 거부 |", "|---|---|---|"]
    for role in sorted({r for r, _ in by_role}):
        lines.append(f"| {role} | {by_role[(role, 'allow')]} | {by_role[(role, 'deny')]} |")
    denied = [a for a in audit if a["decision"] == "deny"]
    if denied:
        lines += ["", "거부된 호출(처음 10건):", ""]
        lines += [f"- {a['role']} {a['tool']} `{a['input'][:60]}` — {a['reason']}" for a in denied[:10]]
    lines.append("")

    lines += ["## 환경", "", "| 항목 | 값 |", "|---|---|"]
    lines += [f"| {k} | {v} |" for k, v in versions.items()]
    lines += [f"| sha256({k}) | `{v}…` |" for k, v in inputs.items()]
    lines.append("")

    # 분리 모드에서는 노트(구현 담당이 씀)보다 조정자의 마지막 응답이 최신이다(split1)
    final = next((s.get("result_text") for s in reversed(sessions) if s.get("result_text")), None)
    lines += ["## 에이전트의 마지막 응답 (검증하지 않은 서술)", "", (final or "(없음)").strip(), ""]
    lines += ["## 에이전트가 쓴 노트 (검증하지 않은 서술)", ""]
    lines += [notes.strip() or "(없음)", ""]

    (out / "report.md").write_text("\n".join(lines), encoding="utf-8")
    (out / "manifest.json").write_text(json.dumps({"versions": versions, "inputs_sha256": inputs, "rust_loc": loc,
                                                    "binary_sha256": _sha256(binary) if binary.is_file() else None},
                                                   ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"report: {out / 'report.md'}")
    return 0
