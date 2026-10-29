"""전 코드 포인트(서로게이트 제외)를 실제 Rust 실행 파일에 넣어 기준 구현과 비교한다 (위험 R1, R2).

각 코드 포인트 c 에 대해 다음 조각을 공백으로 이어 붙인 파일을 만든다.
  "x{c}y"   공백/문장 부호/소문자 처리 (c 가 공백이면 두 단어로 나뉜다)
  "{c}"     단독 (문장 부호면 사라짐)
  "Α{c}Σ"   Final_Sigma 앞 문맥
  "ΑΣ{c}"   Final_Sigma 뒤 문맥
  "{c}Σ"    Final_Sigma 앞 문맥(앞에 아무것도 없음)
파일을 N 조각으로 나눠 각각 --top 큰 값 --json 으로 실행하고, 출력 바이트를 기준 구현 함수 결과와 비교한다.

사용법 (프로젝트 루트에서): python3 verify/all_codepoints.py [--rust rust_app/target/release/wordfreq]
"""

from __future__ import annotations

import argparse
import importlib.util
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("wordfreq_ref", ROOT / "python_src" / "wordfreq.py")
ref = importlib.util.module_from_spec(_spec)
sys.modules["wordfreq_ref"] = ref
_spec.loader.exec_module(ref)

CHUNKS = 16


def pieces(cp: int) -> list[str]:
    c = chr(cp)
    return [f"x{c}y", c, f"Α{c}Σ", f"ΑΣ{c}", f"{c}Σ"]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rust", type=Path, default=ROOT / "rust_app" / "target" / "release" / "wordfreq")
    args = parser.parse_args()
    binary = args.rust.resolve()
    cps = [cp for cp in range(0x110000) if not 0xD800 <= cp <= 0xDFFF]
    size = (len(cps) + CHUNKS - 1) // CHUNKS
    failed = 0
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "all.txt"
        for k in range(CHUNKS):
            part = cps[k * size:(k + 1) * size]
            text = " ".join(p for cp in part for p in pieces(cp))
            path.write_text(text, encoding="utf-8", newline="")
            for as_json in (True, False):
                report = ref.count_words(ref.tokenize(path.read_text(encoding="utf-8")), sys.maxsize)
                expected = (ref.format_json(report) if as_json else ref.format_text(report)).encode("utf-8")
                cmd = [str(binary), str(path), "--top", "9" * 30] + (["--json"] if as_json else [])
                proc = subprocess.run(cmd, capture_output=True, timeout=300)
                ok = proc.returncode == 0 and proc.stdout == expected and not proc.stderr
                label = f"chunk {k:2} U+{part[0]:04X}..U+{part[-1]:04X} {'json' if as_json else 'text'}"
                if ok:
                    print(f"OK   {label} ({len(expected)} bytes)")
                else:
                    failed += 1
                    print(f"FAIL {label} exit={proc.returncode}")
                    exp_lines = expected.split(b"\n") if not as_json else expected.split(b"},{")
                    got_lines = proc.stdout.split(b"\n") if not as_json else proc.stdout.split(b"},{")
                    for e, g in zip(exp_lines, got_lines):
                        if e != g:
                            print(f"     first diff: python={e[:120]!r} rust={g[:120]!r}")
                            break
    print(f"\n{2 * CHUNKS - failed}/{2 * CHUNKS} chunks match")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
