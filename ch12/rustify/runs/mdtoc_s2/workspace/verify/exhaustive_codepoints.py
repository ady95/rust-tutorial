"""모든 코드 포인트(surrogate 제외)를 여러 자리에 넣은 문서에서 Rust 와 기준 구현의 --json 출력을 비교한다.

    python3 verify/exhaustive_codepoints.py
"""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "python_src"))
import mdtoc  # noqa: E402

RUST = ROOT / "rust_app" / "target" / "release" / "mdtoc"
CHUNK = 500

CONTEXTS = [
    "# x{c}y",  # 제목 안
    "# {c}x{c}",  # 앞뒤 공백
    "# x {c}#{c}",  # 닫는 # 앞뒤
    "# x #{c}",
    "#{c}x",  # # 뒤 구분자
    "{c}# x",  # 들여쓰기
    " {c}# x",
    "## a{c}Σ",  # Final_Sigma 맥락
    "## Σ{c}",
    "## Σ{c}a",
    "## ΑΣ{c}",
    "```{c}\n# in\n```\n# out",  # 코드 블록 시작
    "```\n# in\n```{c}\n# out",  # 코드 블록 끝
    "~~~{c}x\n# in\n~~~\n# out",
    "```\n```\n# done",  # 직전 블록 정리
]


def doc_for(cps: list[int]) -> str:
    parts = []
    for cp in cps:
        c = chr(cp)
        for ctx in CONTEXTS:
            parts.append(ctx.replace("{c}", c))
    return "\n".join(parts) + "\n"


def main() -> int:
    cps = [c for c in range(0x110000) if not 0xD800 <= c < 0xE000]
    bad = 0
    for i in range(0, len(cps), CHUNK):
        text = doc_for(cps[i:i + CHUNK])
        data = text.encode("utf-8")
        want = json.dumps(mdtoc.build(text, 1, 6), ensure_ascii=False) + "\n"
        got = subprocess.run([str(RUST), "--json"], input=data, capture_output=True)
        if got.returncode != 0 or got.stdout != want.encode("utf-8"):
            bad += 1
            print("MISMATCH chunk", hex(cps[i]), "-", hex(cps[min(i + CHUNK, len(cps)) - 1]))
    print(f"{len(cps)} code points, {len(CONTEXTS)} contexts, {bad} bad chunks")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
