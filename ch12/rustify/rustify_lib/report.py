"""보고서 (12-3). 수치는 모두 기록 파일에서 계산하고, 에이전트가 쓴 글은 '검증하지 않은 서술'로 따로 싣는다."""

from __future__ import annotations

import json
import re
from pathlib import Path

ORDER = ["baseline", "harness", "fmt", "clippy", "test", "build"]


def _load(path: Path) -> dict | None:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def _jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").split("\n") if line.strip()]


def uncertain_section(notes: str) -> str:
    """port_notes.md 에서 '확신하지 못하는' 절을 찾아 돌려준다."""
    match = re.search(r"^(#+)[^\n]*확신[^\n]*\n(.*?)(?=^\1 |\Z)", notes, re.M | re.S)
    return match.group(2).strip() if match else ""


def write_report(out: Path) -> Path:
    run, summary = _load(out / "run.json"), _load(out / "summary.json")
    sessions = _jsonl(out / "sessions.jsonl")
    gates = sorted(out.glob("gate_round*.json"), key=lambda p: int(re.findall(r"\d+", p.stem)[0]))
    bench, replay = _load(out / "bench.json"), _load(out / "replay.json")
    audit = _jsonl(out / "audit.jsonl")
    lines = [f"# rustify 보고서: {run['project']} ({summary['run']})", ""]

    status = "통과" if summary["stop_reason"] == "gate_passed" else "실패"
    cost = f"{summary['cost_usd']:.2f}달러(추정)" if run["engine"] == "claude" else "구독 요금(토큰만 기록)"
    lines += ["## 요약", "", "| 항목 | 값 |", "|---|---|",
              f"| 결과 | {status} (멈춘 이유: {summary['stop_reason']}) |",
              f"| 엔진·모델 | {run['engine']} · {run['model'] or '기본'} |",
              f"| 시작점 | {'이전 실행 ' + run['from'] + '에서 증분' if run['from'] else '새로 이식'} |",
              f"| 라운드 | {summary['rounds']} |", f"| 비용 | {cost} |",
              f"| 토큰 | {', '.join(f'{k} {v:,}' for k, v in summary['tokens'].items()) or '-'} |",
              f"| 전체 시간 | {summary['wall_s']}초 |",
              f"| 사람 개입 | {summary.get('human_interventions', 0)}회 |",
              *[f"| 경고 | {w} |" for w in summary.get("warnings", [])],
              f"| 확인 게이트(다른 시드) | {'통과' if summary.get('confirm_gate_ok') else '-' if summary.get('confirm_gate_ok') is None else '실패'} |",
              ""]

    lines += ["## 라운드", "", "| 라운드 | 단계 | 상태 | 턴 | 비용 | 게이트 |", "|---|---|---|---|---|---|"]
    rounds = [s for s in sessions if s["stage"] != "analyze"]
    for no, s in enumerate(rounds, 1):
        cost_text = "-" if s["round_cost_usd"] is None else f"{s['round_cost_usd']:.2f}"
        gate_text = "통과" if s["gate_ok"] else "실패: " + ", ".join(s["gate_failing"] or [])
        lines.append(f"| {no} | {s['stage']} | {s['status']} | {s['num_turns']} | {cost_text} | {gate_text} |")
    lines.append("")

    if gates:
        last = _load(gates[-1])
        lines += ["## 마지막 게이트", "", "| 단계 | 결과 | 초 | 마지막 줄 |", "|---|---|---|---|"]
        for step in last["steps"]:
            tail = (step["tail"][-1] if step["tail"] else "").replace("|", "/")[:80]
            lines.append(f"| {step['name']} | {'OK' if step['ok'] else '실패'} | {step['seconds']} | {tail} |")
        lines += ["", f"게이트 격리(bubblewrap, 네트워크 없음): {'예' if last.get('sandboxed') else '아니요'}", ""]

    if bench:
        env = bench["env"]
        lines += ["## 성능", "",
                  f"측정 환경: {env['os']}, {env['cpu']}, {env['rustc']}, {env['python']}, 릴리스 빌드, "
                  f"hyperfine {bench['runs']}회(워밍업 {bench['warmup']}회), 메모리는 {bench['mem_repeat']}회 중앙값", "",
                  "| 케이스 | 입력 | Python 평균 | Rust 평균 | 배수 | Python 메모리 | Rust 메모리 |",
                  "|---|---|---|---|---|---|---|"]
        for c in bench["cases"]:
            if not c["same_output"]:
                lines.append(f"| {c['name']} | {c['input_bytes']:,}B | 출력이 달라 측정 안 함 | | | | |")
                continue
            t, m = c["time"], c["max_rss_kb"]
            lines.append(f"| {c['name']} | {c['input_bytes']:,}B | {t['python']['mean_s'] * 1000:.1f}ms | "
                         f"{t['rust']['mean_s'] * 1000:.1f}ms | {c['speedup']} | {m['python'] / 1024:.1f}MB | "
                         f"{m['rust'] / 1024:.1f}MB |")
        lines.append("")

    art = summary.get("artifacts", {})
    denials = sum(1 for a in audit if a.get("decision") == "deny")
    lines += ["## 보안", "",
              f"- 정책 훅이 거부한 도구 호출: {denials}회 (Codex 엔진은 훅이 없어 기록 없음)" if run["engine"] == "codex"
              else f"- 정책 훅이 거부한 도구 호출: {denials}회",
              f"- 산출물 비밀 검사: {len(art.get('secret_scan', []))}건"
              + "".join(f"\n  - {x['file']}: {x['kind']}" for x in art.get("secret_scan", [])),
              f"- 기록하지 않은 큰 파일: {len(art.get('dropped_large_files', []))}개", ""]

    env = run["env"]
    lines += ["## 재현 정보", "", "| 항목 | 값 |", "|---|---|"]
    lines += [f"| {k} | {v} |" for k, v in env.items() if v]
    lines += [f"| 승인본(baseline.lock) SHA-256 | {run['baseline_sha256']} |",
              f"| 실행 파일 SHA-256 | {art.get('binary_sha256')} |", f"| Cargo.lock SHA-256 | {art.get('cargo_lock_sha256')} |"]
    if replay:
        gates_text = ", ".join(f"시드 {g['seed']}: {'통과' if g['ok'] else '실패'}" for g in replay["gates"])
        lines.append(f"| 다시 빌드·검증(replay) | {gates_text}; 실행 파일 {'같음' if replay['same_binary'] else '다름'} |")
    lines.append("")

    notes_path = out / "workspace" / "reports" / "port_notes.md"
    if notes_path.exists():
        uncertain = uncertain_section(notes_path.read_text(encoding="utf-8"))
        lines += ["## 에이전트가 확신하지 못한 부분(검증하지 않은 서술)", "", uncertain or "(없음)", ""]
    path = out / "report.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path
