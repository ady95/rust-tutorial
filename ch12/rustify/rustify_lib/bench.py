"""성능 측정 (12-3). 9장의 측정 방식(hyperfine + 최대 상주 메모리)을 port.json 의 bench 항목으로 일반화한 것.

- 측정 전에 Python 과 Rust 의 종료 코드·stdout 이 같은지 확인한다. 다르면 그 케이스는 재지 않는다
- Python 은 프로젝트 가상 환경의 인터프리터로 직접 실행한다(uv run 의 준비 시간을 빼려고)
- 측정 환경(OS, CPU, 버전, 반복 횟수)을 결과와 함께 남긴다
"""

from __future__ import annotations

import json
import shlex
import statistics
import subprocess
import tempfile
from pathlib import Path

from .project import load_manifest
from .repro import env_info

DATA = Path.home() / "work" / "rustify_data"


def max_rss_kb(cmd: list[str], cwd: Path, repeat: int) -> int:
    values = []
    for _ in range(repeat):
        proc = subprocess.run(["/usr/bin/time", "-f", "%M", *cmd], cwd=cwd, capture_output=True)
        values.append(int(proc.stderr.decode().strip().splitlines()[-1]))
    return int(statistics.median(values))


def hyperfine(cmds: dict[str, list[str]], cwd: Path, warmup: int, runs: int) -> dict[str, dict]:
    with tempfile.TemporaryDirectory() as tmp:
        export = Path(tmp) / "hf.json"
        args = ["hyperfine", "-N", "--warmup", str(warmup), "--runs", str(runs), "--export-json", str(export),
                "--ignore-failure"]
        for name, cmd in cmds.items():
            args += ["--command-name", name, shlex.join(cmd)]
        subprocess.run(args, cwd=cwd, check=True, stdout=subprocess.DEVNULL)
        data = json.loads(export.read_text())
    return {r["command"]: {"mean_s": r["mean"], "stddev_s": r["stddev"], "median_s": r["median"], "min_s": r["min"],
                           "max_s": r["max"], "runs": len(r["times"])} for r in data["results"]}


def run_bench(workspace: Path, out: Path, runs: int, warmup: int, mem_repeat: int) -> int:
    manifest = load_manifest(workspace)
    spec = manifest.get("bench")
    if not spec:
        print("port.json 에 bench 항목이 없습니다")
        return 2
    data_dir = DATA / manifest["name"]
    if spec.get("generate"):
        subprocess.run([p.format(dir=data_dir) for p in spec["generate"]], cwd=workspace, check=True)
    python = [str(workspace / ".venv" / "bin" / "python"), manifest["python"]]
    rust = [str(workspace / "rust_app" / "target" / "release" / manifest["binary"])]
    results = []
    for case in spec["cases"]:
        args = [a.format(dir=data_dir) for a in case["args"]]
        paths = [Path(a) if Path(a).is_absolute() else workspace / a for a in args]
        size = sum(p.stat().st_size for p in paths if p.is_file())
        py_run = subprocess.run(python + args, cwd=workspace, capture_output=True)
        rs_run = subprocess.run(rust + args, cwd=workspace, capture_output=True)
        row = {"name": case["name"], "args": args, "input_bytes": size, "output_bytes": len(py_run.stdout),
               "same_output": (py_run.returncode, py_run.stdout) == (rs_run.returncode, rs_run.stdout)}
        if not row["same_output"]:
            print(f"{case['name']}: 출력이 달라 측정하지 않음")
            results.append(row)
            continue
        times = hyperfine({"python": python + args, "rust": rust + args}, workspace, warmup, runs)
        row |= {"time": times, "max_rss_kb": {"python": max_rss_kb(python + args, workspace, mem_repeat),
                                               "rust": max_rss_kb(rust + args, workspace, mem_repeat)}}
        row["speedup"] = round(times["python"]["mean_s"] / times["rust"]["mean_s"], 2)
        print(f"{case['name']}: python {times['python']['mean_s']:.4f}s, rust {times['rust']['mean_s']:.4f}s "
              f"({row['speedup']}배), 메모리 {row['max_rss_kb']['python']} KB / {row['max_rss_kb']['rust']} KB")
        results.append(row)
    result = {"build": "release", "runs": runs, "warmup": warmup, "mem_repeat": mem_repeat,
              "env": env_info(workspace), "cases": results}
    (out / "bench.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0
