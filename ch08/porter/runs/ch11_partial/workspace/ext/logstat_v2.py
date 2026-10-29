"""logstat v2: 해석·검증·집계를 Rust(logstat_core)가 하고, 출력 문자열 만들기만 기준 구현의 코드로 한다.

경계: Python -> Rust 는 text(str) 한 번, Rust -> Python 은 요약 dict 하나(레코드 수와 무관).
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "python_src"))

import logstat as module  # noqa: E402
import logstat_core  # noqa: E402


def run(text: str, fmt: str, top_n: int, as_json: bool, strict: bool) -> tuple[int, str, str]:
    error, summary = logstat_core.summarize(text, fmt == "csv", top_n, strict)
    if error is not None:
        return module.EXIT_INPUT_ERROR, "", f"logstat: error: {error}\n"
    if as_json:
        out = module.json.dumps(summary, ensure_ascii=False, separators=(",", ":")) + "\n"
    else:
        out = module.format_text(summary)
    return module.EXIT_OK, out, ""


module.run = run

if __name__ == "__main__":
    sys.exit(module.main())
