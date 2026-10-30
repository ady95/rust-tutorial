"""실행 기록 폴더들의 summary.json·bench.json 을 표 하나로 모은다(부록 A): collect_runs.py <runs 폴더>"""
import json
import sys
from pathlib import Path


def load(path: Path) -> dict | None:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def row(run_dir: Path) -> list[str] | None:
    summary = load(run_dir / "summary.json")
    if summary is None:
        return None
    bench = load(run_dir / "bench.json")
    cost = f"{summary['cost_usd']:.2f}" if summary["engine"] == "claude" else "-"
    confirm = {True: "통과", False: "실패", None: "-"}[summary.get("confirm_gate_ok")]
    size = summary.get("artifacts", {}).get("binary_bytes")
    speedup = bench["cases"][0]["speedup"] if bench else None
    return [run_dir.name, summary["engine"], summary["stop_reason"], str(summary["rounds"]),
            cost, f"{summary['wall_s']:.1f}", str(summary["human_interventions"]), confirm,
            f"{size:,}" if size else "-", f"{speedup:.2f}" if speedup else "-"]


HEADER = ["실행", "엔진", "멈춘 이유", "라운드", "비용(추정, 달러)", "시간(초)",
          "개입", "확인 게이트", "실행 파일(바이트)", "큰 입력 배수"]

rows = [r for d in sorted(Path(sys.argv[1]).iterdir()) if d.is_dir() and (r := row(d))]
print("| " + " | ".join(HEADER) + " |")
print("|" + "---|" * len(HEADER))
for r in rows:
    print("| " + " | ".join(r) + " |")
