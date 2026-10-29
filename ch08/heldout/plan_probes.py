"""계획(08-2)이 짚었지만 게이트에는 없는 입력으로 Python 기준 구현과 Rust 구현을 비교한다 (08-3 사후 점검).

이식 계획의 위험 목록 R1(공백), R2(어말 시그마), R4(argparse), R5(pathlib)에서 뽑은 입력이다.
에이전트는 계획을 보았으므로 '숨긴' 평가는 아니다. 계획에 적힌 위험이 구현에 반영됐는지를 본다.

사용법: python3 plan_probes.py <Rust 실행 파일> --reference <python_src/wordfreq.py> --project <프로젝트 폴더> [--out result.json]
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

# (이름, 인자, 입력 텍스트 또는 None) — 인자 안의 {f} 는 입력 파일 경로
PROBES: list[tuple[str, list[str], str | None]] = [
    ("ws-u001c-u001f", ["{f}"], "a\x1cb a\x1db a\x1eb a\x1fb"),
    ("ws-u000b-u0085-u3000", ["{f}"], "a\x0bb a\x85b a　b"),
    ("not-ws-u200b-u180e", ["{f}"], "a​b a᠎b"),
    ("sigma-final", ["{f}"], "ΑΣ Σ ΑΣΑ ΑΣ'Β ΆΣ ΑΣ́"),
    ("path-trailing-slash", ["tests/fixtures/basic.txt/"], None),
    ("path-trailing-dot", ["tests/fixtures/basic.txt/."], None),
    ("path-dot-segment", ["./tests/fixtures/basic.txt"], None),
    ("path-empty", [""], None),
    ("path-missing-slash", ["nope.txt/"], None),
    ("abbrev-to", ["tests/fixtures/basic.txt", "--to", "2"], None),
    ("abbrev-js", ["tests/fixtures/basic.txt", "--js"], None),
    ("abbrev-t-equals", ["tests/fixtures/basic.txt", "--t=2"], None),
    ("top-last-wins", ["tests/fixtures/basic.txt", "--top", "1", "--top", "3"], None),
    ("double-dash-dash-name", ["--", "-x"], None),
    ("negative-like-file", ["-5"], None),
    ("usage-extra-positional", ["tests/fixtures/basic.txt", "extra.txt"], None),
    ("usage-json-value", ["tests/fixtures/basic.txt", "--json=1"], None),
    ("usage-top-missing", ["tests/fixtures/basic.txt", "--top"], None),
    ("usage-dash-option", ["-x.txt"], None),
    ("help", ["-h"], None),
]


def run(cmd: list[str], cwd: Path) -> tuple[int, bytes, bytes]:
    proc = subprocess.run(cmd, cwd=cwd, capture_output=True, timeout=60)
    return proc.returncode, proc.stdout, proc.stderr


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("rust", type=Path)
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    rows = []
    with tempfile.TemporaryDirectory() as tmp:
        for name, probe_args, text in PROBES:
            path = Path(tmp) / f"{name}.txt"
            if text is not None:
                path.write_text(text, encoding="utf-8")
            argv = [a.format(f=path) for a in probe_args]
            py = run([sys.executable, str(args.reference.resolve()), *argv], args.project)
            rs = run([str(args.rust.resolve()), *argv], args.project)
            if py[0] == 2 or name == "help":
                # 계약 4절: 인자 오류는 종료 코드만(stderr 비어 있지 않음). 도움말 문구는 계약에 없다
                same = py[0] == rs[0] and (bool(rs[2]) if py[0] == 2 else True)
                rule = "exit-only"
            else:
                same = py == rs
                rule = "exact"
            rows.append({"probe": name, "rule": rule, "same": same, "python_exit": py[0], "rust_exit": rs[0]})
    for row in rows:
        print(f"{'OK  ' if row['same'] else 'DIFF'} {row['probe']:<24} python={row['python_exit']} rust={row['rust_exit']}")
    same = sum(r["same"] for r in rows)
    print(f"\n{same}/{len(rows)} plan probes match")
    if args.out:
        args.out.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0 if same == len(rows) else 1


if __name__ == "__main__":
    sys.exit(main())
