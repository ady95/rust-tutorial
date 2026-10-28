"""단어 모양 하나를 정해 모든 코드 포인트로 단어를 만들고 Python 과 Rust 의 결과를 비교한다 (07-2).

Hypothesis 가 찾은 최소 입력(예: "AࢗΣ")을 일반화해, 같은 모양에서 몇 개의 코드 포인트가 문제인지 센다.
사용법: python3 sweep_pattern.py <Rust 실행 파일> --pattern "A{c}Σ"
"""

import argparse
import json
import subprocess
import sys
import tempfile
import unicodedata
from pathlib import Path

from equivalence import REFERENCE


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser()
    parser.add_argument("rust", type=Path)
    parser.add_argument("--pattern", default="A{c}Σ")
    args = parser.parse_args()
    cps = [cp for cp in range(0x110000) if not 0xD800 <= cp <= 0xDFFF]
    # 공백·문장 부호 글자는 단어를 쪼개거나 깎으므로 따로 실행할 필요가 없도록 한 줄에 하나씩 둔다
    words = [args.pattern.format(c=chr(cp)) for cp in cps]
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "in.txt"
        path.write_text("\n".join(words) + "\n", encoding="utf-8")
        cmd = [str(path), "--json", "--top", "100000000"]
        py = json.loads(subprocess.run([sys.executable, str(REFERENCE), *cmd], capture_output=True).stdout)
        rs_proc = subprocess.run([str(args.rust.resolve()), *cmd], capture_output=True)
    if rs_proc.returncode != 0:
        print(f"rust exit {rs_proc.returncode}: {rs_proc.stderr[:200]!r}")
        return 1
    rs = json.loads(rs_proc.stdout)
    pw = {d["word"] for d in py["top"]}
    rw = {d["word"] for d in rs["top"]}
    only_py = sorted(pw - rw)
    cats: dict[str, int] = {}
    for word in only_py:
        mid = word[1:-1] if len(word) >= 3 else word
        for ch in mid:
            cats[unicodedata.category(ch)] = cats.get(unicodedata.category(ch), 0) + 1
    print(json.dumps({"pattern": args.pattern, "words": len(words), "only_python": len(only_py),
                      "only_rust": len(rw - pw), "python_categories_of_middle": cats,
                      "sample": [[f"U+{ord(c):04X}" for c in w] for w in only_py[:5]]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
