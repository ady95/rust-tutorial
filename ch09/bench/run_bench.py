"""처리량·지연시간·메모리를 측정한다 (09-3, 09-4).

- 시간: hyperfine(셸 없이 실행, 워밍업 후 반복). 평균·표준편차·중앙값·최솟값을 기록하고 처리량(레코드/초)을 계산
- 메모리: /usr/bin/time -f %M 으로 최대 상주 메모리(RSS)를 반복 측정해 중앙값
- 모든 구현의 stdout 이 같은지 먼저 확인한다(다르면 측정하지 않는다)

사용법:
  python3 run_bench.py --impl py="python3 ../logstat/python_src/logstat.py" --impl rs=../logstat/rust_app/target/release/logstat \
      --data ~/work/ch09_data/logs_1000000.csv --records 999000 --runs 10 --out results/1m_csv.json
"""

from __future__ import annotations

import argparse
import json
import platform
import shlex
import statistics
import subprocess
import sys
import tempfile
from pathlib import Path


def run_once(cmd: list[str]) -> bytes:
    return subprocess.run(cmd, capture_output=True, check=True).stdout


def max_rss_kb(cmd: list[str], repeat: int) -> int:
    values = []
    for _ in range(repeat):
        proc = subprocess.run(["/usr/bin/time", "-f", "%M", *cmd], capture_output=True, check=True)
        values.append(int(proc.stderr.decode().strip().splitlines()[-1]))
    return int(statistics.median(values))


def hyperfine(cmds: dict[str, list[str]], warmup: int, runs: int) -> dict[str, dict]:
    with tempfile.TemporaryDirectory() as tmp:
        export = Path(tmp) / "hf.json"
        args = ["hyperfine", "-N", "--warmup", str(warmup), "--runs", str(runs), "--export-json", str(export)]
        for name, cmd in cmds.items():
            args += ["--command-name", name, shlex.join(cmd)]
        subprocess.run(args, check=True, stdout=subprocess.DEVNULL)
        data = json.loads(export.read_text())
    out = {}
    for result in data["results"]:
        times = result["times"]
        out[result["command"]] = {"mean_s": result["mean"], "stddev_s": result["stddev"], "median_s": result["median"],
                                  "min_s": result["min"], "max_s": result["max"], "runs": len(times)}
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--impl", action="append", required=True, help="이름=명령")
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--records", type=int, required=True, help="파일의 레코드 수(처리량 계산용)")
    parser.add_argument("--extra", default="--top 10", help="모든 구현에 붙일 인자")
    parser.add_argument("--warmup", type=int, default=2)
    parser.add_argument("--runs", type=int, default=10)
    parser.add_argument("--rss-repeat", type=int, default=3)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    cmds = {}
    for spec in args.impl:
        name, cmd = spec.split("=", 1)
        cmds[name] = [*shlex.split(cmd), str(args.data), *shlex.split(args.extra)]
    outputs = {name: run_once(cmd) for name, cmd in cmds.items()}
    first = next(iter(outputs.values()))
    mismatched = [name for name, out in outputs.items() if out != first]
    if mismatched:
        print(f"출력이 다른 구현이 있어 측정하지 않습니다: {mismatched}", file=sys.stderr)
        return 1

    timing = hyperfine(cmds, args.warmup, args.runs)
    results = {}
    for name, cmd in cmds.items():
        t = timing[name]
        results[name] = t | {"records_per_s": args.records / t["mean_s"], "max_rss_kb": max_rss_kb(cmd, args.rss_repeat),
                             "command": shlex.join(cmd)}
    report = {"data": str(args.data), "data_bytes": args.data.stat().st_size, "records": args.records,
              "warmup": args.warmup, "machine": platform.platform(), "results": results}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{args.data.name} ({args.data.stat().st_size:,} B, {args.records:,} records)")
    print(f"{'impl':<12}{'mean s':>10}{'± sd':>9}{'median':>9}{'rec/s':>13}{'RSS MB':>9}")
    for name, r in results.items():
        print(f"{name:<12}{r['mean_s']:>10.3f}{r['stddev_s']:>9.3f}{r['median_s']:>9.3f}"
              f"{r['records_per_s']:>13,.0f}{r['max_rss_kb'] / 1024:>9.1f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
