"""숨긴 평가 (08-3). 변환 루프가 끝난 뒤에만 실행하고, 에이전트에게는 보여 주지 않는다.

05-5와 07장에서 찾은 결함을 다시 일으키는 입력들이다. 게이트(비교 케이스·시나리오·무작위 비교)를 통과한
구현이 이 입력에서도 같은지 본다.
- shapes : 모든 코드 포인트 c 로 단어 모양 4가지(A<c>B, <c>Σ, Σ<c>, A<c>Σ)를 만들어 비교(07-2 sweep 의 일반화)
- files  : 07-1 의 추가 케이스 입력(ʕΣ, 새 글자 9개)

사용법: python3 evaluate.py <Rust 실행 파일> --reference <python_src/wordfreq.py> [--out result.json]
종료 코드: 0 = 모두 같음, 1 = 다름 있음
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
SHAPES = ["A{c}B", "{c}Σ", "Σ{c}", "A{c}Σ"]
FILES = [HERE.parents[1] / "ch07" / "golden" / "fixtures" / name for name in ("u0295_sigma.txt", "new_letters.txt")]
ARGS = ["--json", "--top", "100000000"]


def run(cmd: list[str]) -> tuple[int, bytes]:
    proc = subprocess.run(cmd, capture_output=True, timeout=600)
    return proc.returncode, proc.stdout


def shape(binary: Path, reference: Path, pattern: str, tmp: Path) -> dict:
    cps = [cp for cp in range(0x110000) if not 0xD800 <= cp <= 0xDFFF]
    path = tmp / "shape.txt"
    path.write_text("\n".join(pattern.format(c=chr(cp)) for cp in cps) + "\n", encoding="utf-8")
    py_code, py_out = run([sys.executable, str(reference), str(path), *ARGS])
    rs_code, rs_out = run([str(binary), str(path), *ARGS])
    row = {"input": f"shape {pattern}", "same": (py_code, py_out) == (rs_code, rs_out), "rust_exit": rs_code}
    if rs_code == 0 and py_code == 0:
        py_words = {d["word"]: d["count"] for d in json.loads(py_out)["top"]}
        rs_words = {d["word"]: d["count"] for d in json.loads(rs_out)["top"]}
        diff = {w for w in py_words.keys() | rs_words.keys() if py_words.get(w) != rs_words.get(w)}
        # 단어 모양에서 c 자리의 코드 포인트를 거꾸로 찾는다
        bad = sorted({cp for cp in cps if pattern.format(c=chr(cp)).lower() in diff or pattern.format(c=chr(cp)) in diff})
        row["differing_words"] = len(diff)
        row["differing_codepoints"] = len(bad)
        row["sample"] = [f"U+{cp:04X}" for cp in bad[:5]]
    return row


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("rust", type=Path)
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    binary = args.rust.resolve()
    rows = []
    with tempfile.TemporaryDirectory() as tmp:
        for pattern in SHAPES:
            rows.append(shape(binary, args.reference, pattern, Path(tmp)))
    for path in FILES:
        py = run([sys.executable, str(args.reference), str(path), *ARGS])
        rs = run([str(binary), str(path), *ARGS])
        rows.append({"input": path.name, "same": py == rs, "rust_exit": rs[0]})
    for row in rows:
        detail = "" if row["same"] else f"  rust_exit={row['rust_exit']} codepoints={row.get('differing_codepoints', '-')} {row.get('sample', '')}"
        print(f"{'OK  ' if row['same'] else 'DIFF'} {row['input']}{detail}")
    same = sum(r["same"] for r in rows)
    print(f"\n{same}/{len(rows)} held-out inputs match")
    if args.out:
        args.out.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0 if same == len(rows) else 1


if __name__ == "__main__":
    sys.exit(main())
