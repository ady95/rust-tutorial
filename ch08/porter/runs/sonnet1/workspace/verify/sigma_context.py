"""Final_Sigma 문맥 전수 비교: 모든 코드 포인트 c 를 Σ 앞뒤에 놓은 단어를 Python 과 Rust 로 소문자 변환해 비교한다.

단어 형태: c+Σ, αΣ+c, α+c+Σ, αΣ+c+α, Σ+c+α, ΑΣ+c+Α (c 는 공백·문장 부호·서로게이트 제외).
사용법: python3 verify/sigma_context.py rust_app/target/release/wordfreq
"""

import json
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "python_src"))
import wordfreq  # noqa: E402

binary = sys.argv[1]
chars = [chr(c) for c in range(0x110000) if not 0xD800 <= c <= 0xDFFF]
chars = [c for c in chars if not c.isspace() and c not in wordfreq.PUNCTUATION]
SHAPES = ["{c}Σ", "αΣ{c}", "α{c}Σ", "αΣ{c}α", "Σ{c}α", "ΑΣ{c}Α", "{c}{c}Σ", "αΣ{c}{c}"]
words = [s.format(c=c) for c in chars for s in SHAPES]
text = " ".join(words)
expected = Counter(w for w in wordfreq.tokenize(text))
with tempfile.TemporaryDirectory() as tmp:
    path = Path(tmp) / "s.txt"
    path.write_text(text, encoding="utf-8")
    out = subprocess.run([binary, str(path), "--top", "9" * 30, "--json"], capture_output=True, check=True).stdout
actual = Counter({i["word"]: i["count"] for i in json.loads(out)["top"]})
missing, extra = expected - actual, actual - expected
print("words tested:", len(words), "python-only:", len(missing), "rust-only:", len(extra))
for w in sorted(missing)[:40]:
    print("  python-only", [f"U+{ord(c):04X}" for c in w])
for w in sorted(extra)[:40]:
    print("  rust-only  ", [f"U+{ord(c):04X}" for c in w])
sys.exit(1 if missing or extra else 0)
