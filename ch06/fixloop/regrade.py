"""저장된 실행 결과(runs/<이름>/lib.rs)를 현재 채점 기준(run_agent.CLI_CASES)으로 다시 채점한다.

채점 케이스를 나중에 추가했을 때 쓴다. 결과는 metrics.json 의 regrade 항목에 덧붙인다.
사용법 (WSL·Linux, ch06/fixloop 에서): python3 regrade.py runA_shell runC_hooks_only ... [--answer]
"""

import json
import shutil
import sys
from pathlib import Path

import run_agent

HERE = Path(__file__).resolve().parent


def regrade(lib: Path, work: Path) -> dict:
    if work.exists():
        shutil.rmtree(work)
    shutil.copytree(run_agent.TASK, work)
    shutil.copy(lib, work / "src" / "lib.rs")
    return run_agent.grade(work)


def main() -> int:
    work = Path.home() / "work" / "ch06_regrade"
    for name in sys.argv[1:]:
        if name == "--answer":
            print("answer", json.dumps(regrade(HERE / "answer" / "src" / "lib.rs", work), ensure_ascii=False))
            continue
        out = HERE / "runs" / name
        result = regrade(out / "lib.rs", work)
        metrics_path = out / "metrics.json"
        if metrics_path.exists():
            metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
            metrics["regrade"] = {"cli_cases": len(run_agent.CLI_CASES), **result}
            metrics_path.write_text(json.dumps(metrics, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(name, json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
