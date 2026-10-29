"""사람의 파일이나 하네스가 바뀐 작업 폴더에서 게이트가 어떻게 멈추는지 확인한다 (12-4).

    uv run python examples/protected_probe.py <작업 폴더>     # 예: ~/work/rustify_ws/mdtoc_s1-replay

작업 폴더를 임시로 복사해 (1) 비교 케이스 하나를 지운 경우 (2) 비교 하네스를 고친 경우를 만들고 게이트를 돌린다.
에이전트는 부르지 않는다.
"""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from rustify_lib import gate as gate_mod  # noqa: E402
from rustify_lib.project import load_manifest  # noqa: E402


def main() -> int:
    source = Path(sys.argv[1]).expanduser().resolve()
    harness_sha = gate_mod.harness_digest(source)
    manifest = load_manifest(source)
    with tempfile.TemporaryDirectory(dir=source.parent) as tmp:
        for label, change in [("케이스 삭제", "cases"), ("하네스 수정", "harness")]:
            ws = Path(tmp) / change
            shutil.copytree(source, ws, symlinks=True, ignore=shutil.ignore_patterns("target"))
            if change == "cases":  # 에이전트가 통과하지 못하는 케이스를 지웠다고 가정
                path = ws / "tests" / "cases.json"
                cases = json.loads(path.read_text(encoding="utf-8"))
                path.write_text(json.dumps(cases[1:], ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
            else:  # 비교 도구가 늘 성공하도록 고쳤다고 가정
                path = ws / ".rustify" / "compare_cli.py"
                path.write_text(path.read_text(encoding="utf-8").replace("return 0 if passed == len(cases) else 1",
                                                                         "return 0"), encoding="utf-8")
            result = gate_mod.run_gate(ws, manifest, harness_sha)
            steps = ", ".join(f"{s.name}={'OK' if s.ok else '실패'}" for s in result.steps)
            print(f"{label}: ok={result.ok}, protected_changed={result.protected_changed}, 단계: {steps}")
            for step in result.steps:
                for line in step.tail[-2:]:
                    print(f"    {step.name}: {line}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
