"""모든 코드 포인트(서로게이트 제외)에 대해 기준 구현 CLI 와 Rust 실행 파일의 출력을 비교한다.

글자 c 마다 아래 토큰을 공백으로 이어 붙인 파일을 평면(0x10000 글자) 단위로 만들어 두 프로그램에 넣는다.
  c, "x{c}y"          공백 판단(str.split), 문장 부호 떼기, 소문자 변환
  "A{c}Σ", "{c}Σ"     Final_Sigma 의 앞쪽 문맥(Case_Ignorable, Cased)
  "AΣ{c}", "AΣ{c}B"   Final_Sigma 의 뒤쪽 문맥
--top 은 아주 큰 값, 텍스트와 JSON 두 형식 모두 비교한다.

사용법: python3 verify/check_all_codepoints.py [--rust rust_app/target/release/wordfreq]
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REFERENCE = ROOT / "python_src" / "wordfreq.py"


def tokens(c: int) -> list[str]:
    ch = chr(c)
    return [ch, f"x{ch}y", f"A{ch}Σ", f"{ch}Σ", f"AΣ{ch}", f"AΣ{ch}B"]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rust", type=Path, default=ROOT / "rust_app" / "target" / "release" / "wordfreq")
    args = parser.parse_args()
    binary = str(args.rust.resolve())
    fails = 0
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "plane.txt"
        for plane in range(17):
            cps = [c for c in range(plane << 16, (plane + 1) << 16) if not 0xD800 <= c <= 0xDFFF]
            path.write_text(" ".join(t for c in cps for t in tokens(c)), encoding="utf-8", newline="")
            for extra in ([], ["--json"]):
                cmd = [str(path), "--top", "9" * 30, *extra]
                py = subprocess.run([sys.executable, str(REFERENCE), *cmd], capture_output=True)
                rs = subprocess.run([binary, *cmd], capture_output=True)
                same = (py.returncode, py.stdout, py.stderr) == (rs.returncode, rs.stdout, rs.stderr)
                fails += not same
                print(f"{'OK  ' if same else 'FAIL'} plane {plane:2d} {' '.join(extra) or 'text'} "
                      f"({len(py.stdout)} bytes)")
                if not same:
                    py_lines, rs_lines = py.stdout.splitlines(), rs.stdout.splitlines()
                    diff = [(a, b) for a, b in zip(py_lines, rs_lines) if a != b][:5]
                    print(f"     exit python={py.returncode} rust={rs.returncode}; first diffs: {diff!r}")
    print("all code points match" if not fails else f"{fails} runs differ")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
