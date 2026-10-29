"""모든 코드 포인트(surrogate 제외)를 여러 자리에 넣은 문서로 Python 기준 구현과 Rust 바이너리를 비교한다.

    python3 verify/exhaustive_codepoints.py [--step N]

자리: 제목 안(lower, \\w), 앞뒤(strip), 닫는 # 앞뒤, # 뒤 구분자, 들여쓰기, Σ 맥락(Final_Sigma).
Rust 의 --json 출력이 기준 구현 build() 의 json.dumps 결과와 바이트 단위로 같아야 한다.
fence 닫기 뒤 자리는 상태가 이어지므로 코드 포인트마다 문서를 따로 만든다(공백류와 몇 글자만).
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "python_src"))
import mdtoc  # noqa: E402

RUST = ROOT / "rust_app" / "target" / "release" / "mdtoc"
TEMPLATES = [
    "# a{c}b",
    "# {c}x{c}",
    "# a #{c}",
    "# a{c}# ",
    "#{c}x",
    "{c}# x",
    " {c}# x",
    "# a{c}Σ",
    "# 1{c}Σ",
    "# AΣ{c}",
    "# AΣ{c}A",
    "# Σ{c}Σ",
]


def rust(text: str, *args: str) -> tuple[int, bytes, bytes]:
    proc = subprocess.run([str(RUST), *args], input=text.encode("utf-8"), capture_output=True, timeout=300)
    return proc.returncode, proc.stdout, proc.stderr


def expected(text: str) -> bytes:
    return (json.dumps(mdtoc.build(text, 1, 6), ensure_ascii=False) + "\n").encode("utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--step", type=int, default=1, help="코드 포인트 간격(빠른 시험용)")
    args = parser.parse_args()
    if sys.version_info[:2] != (3, 12):
        print(f"warning: Python {sys.version_info[:3]} (기준은 3.12), unidata {unicodedata.unidata_version}")
    codes = [c for c in range(0, 0x110000, args.step) if not 0xD800 <= c < 0xE000]
    failures = 0
    for lo in range(0, len(codes), 20000):
        chunk = codes[lo:lo + 20000]
        text = "\n".join(t.replace("{c}", chr(c)) for c in chunk for t in TEMPLATES) + "\n"
        code, out, err = rust(text, "--json")
        want = expected(text)
        if code != 0 or out != want:
            failures += 1
            # 어느 코드 포인트인지 좁힌다
            for c in chunk:
                one = "\n".join(t.replace("{c}", chr(c)) for t in TEMPLATES) + "\n"
                if rust(one, "--json")[1] != expected(one):
                    print(f"MISMATCH U+{c:04X} {unicodedata.category(chr(c))}")
                    break
        print(f"chunk U+{chunk[0]:04X}..U+{chunk[-1]:04X}: {'ok' if code == 0 and out == want else 'FAIL'}", flush=True)
    # fence 를 닫는 줄 뒤 자리
    fence_codes = [c for c in codes if chr(c).isspace()] + [ord(x) for x in "x`~#"]
    for c in fence_codes:
        for open_mark in ("```", "~~~~"):
            for close in (open_mark, open_mark + "~`"[open_mark[0] == "`"]):
                text = f"{open_mark}\n{close}{chr(c)}\n# t{chr(c)}\n{open_mark}{chr(c)}\n# u\n"
                if rust(text, "--json")[1] != expected(text):
                    failures += 1
                    print(f"FENCE MISMATCH U+{c:04X} {text!r}")
    print("exhaustive: " + ("OK" if not failures else f"{failures} failures"))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
