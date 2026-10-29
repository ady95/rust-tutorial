"""logstat v1: 해석·검증(read_csv/read_jsonl)만 Rust(logstat_core)가 하고, 집계와 출력은 기준 구현의 함수를 쓴다.

경계: Python -> Rust 는 text(str) 한 번, Rust -> Python 은 레코드마다 (번호, Record 또는 BadRecord) 객체.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "python_src"))

import logstat as module  # noqa: E402
import logstat_core  # noqa: E402


def run(text: str, fmt: str, top_n: int, as_json: bool, strict: bool) -> tuple[int, str, str]:
    if fmt == "csv":
        rows, header_error = logstat_core.read_csv(text, module.Record, module.BadRecord)
        if header_error:
            return module.EXIT_INPUT_ERROR, "", f"logstat: error: {header_error}\n"
    else:
        rows = logstat_core.read_jsonl(text, module.Record, module.BadRecord)
    records = []
    skipped = 0
    for number, item in rows:
        if isinstance(item, module.BadRecord):
            if strict:
                return module.EXIT_INPUT_ERROR, "", f"logstat: error: record {number}: {item}\n"
            skipped += 1
        else:
            records.append(item)
    summary = module.summarize(records, skipped, top_n)
    if as_json:
        out = module.json.dumps(summary, ensure_ascii=False, separators=(",", ":")) + "\n"
    else:
        out = module.format_text(summary)
    return module.EXIT_OK, out, ""


module.run = run

if __name__ == "__main__":
    sys.exit(module.main())
