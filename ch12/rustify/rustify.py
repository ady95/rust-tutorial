"""rustify: 사람은 Python 만 개발하고, Rust 버전은 에이전트가 만들고 도구가 검증한다 (12장).

    uv run python rustify.py check   <프로젝트>                      # 12-1 입력 검사(비용 0)
    uv run python rustify.py approve <프로젝트>                      # 12-1 사람이 검토 후 승인(baseline.lock)
    uv run python rustify.py run     <프로젝트> --run <이름> [--from <이전 실행>] [--engine claude|codex]
                                                                    # 12-2 생성·컴파일·수정·검증
    uv run python rustify.py bench   --run <이름>                     # 12-3 성능 측정
    uv run python rustify.py report  --run <이름>                     # 12-3 보고서
    uv run python rustify.py replay  --run <이름>                     # 12-4 기록만으로 다시 빌드·검증

작업 폴더는 ~/work/rustify_ws/<이름>, 기록은 runs/<이름>/. Linux·WSL 기준.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from rustify_lib.bench import run_bench
from rustify_lib.pipeline import RUNS, WORK, replay, run_pipeline
from rustify_lib.project import approve, check_project
from rustify_lib.report import write_report


def main() -> int:
    parser = argparse.ArgumentParser(description="Python → Rust automatic porting system (ch12)")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("check", "approve"):
        sub.add_parser(name).add_argument("project", type=Path)
    run = sub.add_parser("run")
    run.add_argument("project", type=Path)
    run.add_argument("--run", required=True)
    run.add_argument("--from", dest="base",
                     help="이전 실행 이름(또는 작업 폴더 경로). 그 Rust 구현에서 시작한다(증분 이식)")
    run.add_argument("--engine", choices=["claude", "codex"], default="claude")
    run.add_argument("--model", help="claude: sonnet·opus 등(기본 sonnet), codex: 기본은 Codex 설정")
    run.add_argument("--plan", type=Path, help="분석 단계 대신 쓸 이식 계획(plan.json)")
    run.add_argument("--analyze", action=argparse.BooleanOptionalAction, default=True)
    run.add_argument("--followup", action=argparse.BooleanOptionalAction, default=True,
                     help="게이트 통과 뒤 에이전트의 불확실 항목을 확인하는 라운드")
    run.add_argument("--allow-crates", action="store_true", help="crates.io 접속 허용")
    run.add_argument("--budget", type=float, default=5.0, help="달러(Claude 엔진의 추정 비용 기준)")
    run.add_argument("--max-rounds", type=int, default=5)
    run.add_argument("--max-turns", type=int, default=100)
    run.add_argument("--max-minutes", type=float, help="전체 시간 상한(라운드 사이에서 확인)")
    run.add_argument("--no-gate-sandbox", action="store_true", help="게이트를 bubblewrap 없이 실행")
    bench = sub.add_parser("bench")
    bench.add_argument("--run", required=True)
    bench.add_argument("--runs", type=int, default=10)
    bench.add_argument("--warmup", type=int, default=2)
    bench.add_argument("--mem-repeat", type=int, default=5)
    sub.add_parser("report").add_argument("--run", required=True)
    rep = sub.add_parser("replay")
    rep.add_argument("--run", required=True)
    rep.add_argument("--no-gate-sandbox", action="store_true")
    args = parser.parse_args()

    if args.command == "check":
        report = check_project(args.project.resolve())
        print(report.render())
        return 0 if report.ok else 1
    if args.command == "approve":
        return approve(args.project.resolve())
    if args.command == "run":
        return asyncio.run(run_pipeline(args))
    if args.command == "bench":
        return run_bench(WORK / args.run, RUNS / args.run, args.runs, args.warmup, args.mem_repeat)
    if args.command == "replay":
        return asyncio.run(replay(args))
    print(write_report(RUNS / args.run))
    return 0


if __name__ == "__main__":
    sys.exit(main())
