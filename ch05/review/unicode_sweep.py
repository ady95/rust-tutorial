"""모든 Unicode 코드 포인트로 만든 입력을 Python 기준 구현과 Rust 구현에 넣어 비교한다 (05-5).

코드 포인트마다 세 단어를 만든다: "A<c>B", "<c>Σ", "Σ<c>".
공백 판정, 앞뒤 문장 부호 제거, 소문자 변환, 어말 시그마 규칙을 한꺼번에 시험한다.

사용법 (ch05/wordfreq 에서):
    uv run python ../review/unicode_sweep.py <Rust 실행 파일> [<Rust 실행 파일> ...]
"""

import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
INPUT = HERE / "data" / "all_codepoints.txt"


def make_input() -> None:
    INPUT.parent.mkdir(exist_ok=True)
    words = []
    for cp in range(0x110000):
        if 0xD800 <= cp <= 0xDFFF:  # 서로게이트는 UTF-8 로 쓸 수 없다
            continue
        c = chr(cp)
        words += [f"A{c}B", f"{c}Σ", f"Σ{c}"]
    INPUT.write_text(" ".join(words) + "\n", encoding="utf-8", newline="\n")


def run(cmd: list[str]) -> tuple[int, bytes]:
    proc = subprocess.run([*cmd, str(INPUT), "--json", "--top", "100000000"], capture_output=True)
    return proc.returncode, proc.stdout


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    if not INPUT.exists():
        make_input()
    print(f"input: {INPUT.stat().st_size:,} bytes")
    expected = run([sys.executable, "python_src/wordfreq.py"])
    for exe in sys.argv[1:]:
        try:
            got = run([str(Path(exe).resolve())])
        except OSError as err:
            print(f"ERROR {exe}: {err}")
            continue
        if got == expected:
            print(f"same  {exe}")
            continue
        print(f"DIFF  {exe} (exit python={expected[0]} rust={got[0]})")
        if got[0] != 0:
            continue
        py_words = {d["word"] for d in json.loads(expected[1])["top"]}
        rs_words = {d["word"] for d in json.loads(got[1])["top"]}
        only_py, only_rs = sorted(py_words - rs_words), sorted(rs_words - py_words)
        print(f"      Python 에만 있는 단어 {len(only_py)}개, Rust 에만 있는 단어 {len(only_rs)}개")
        for word in only_py[:3]:
            print("      예(Python):", [hex(ord(ch)) for ch in word])
    return 0


if __name__ == "__main__":
    sys.exit(main())
