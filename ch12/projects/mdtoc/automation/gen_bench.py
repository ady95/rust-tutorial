"""성능 측정용 큰 Markdown 문서를 만든다(고정 시드라 매번 같은 파일).

    uv run python automation/gen_bench.py <폴더>     # <폴더>/large.md (약 20MB, 제목 약 6만 개)
"""

from __future__ import annotations

import random
import sys
from pathlib import Path

WORDS = ["install", "usage", "설정", "예제", "API", "Straße", "İndex", "naïve", "v1.2", "FAQ", "로그", "_internal"]


def main() -> int:
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    rng = random.Random(20261030)
    lines: list[str] = []
    while len(lines) < 400_000:
        kind = rng.random()
        if kind < 0.15:
            lines.append("#" * rng.randint(1, 6) + " " + " ".join(rng.choices(WORDS, k=rng.randint(1, 5))))
        elif kind < 0.18:
            body = ["# not a heading " + str(rng.randint(0, 99)) for _ in range(rng.randint(1, 8))]
            lines += ["```python", *body, "```"]
        else:
            lines.append(" ".join(rng.choices(WORDS, k=rng.randint(3, 15))) + ".")
    (out / "large.md").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
