"""모든 코드 포인트에 대해 Python str.lower() 와 Rust 바이너리의 소문자 변환을 비교한다.

각 글자를 한 단어로 넣고(공백·문장 부호·서로게이트 제외), 기준 구현이 만드는 단어 다중집합과
Rust 출력의 다중집합을 비교한다. 차이가 나는 글자를 U+XXXX 로 출력한다.
사용법: python3 verify/lower_table.py rust_app/target/release/wordfreq
"""

import json
import subprocess
import sys
import tempfile
import unicodedata
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "python_src"))
import wordfreq  # noqa: E402

binary = sys.argv[1]
print("python", sys.version.split()[0], "unicode", unicodedata.unidata_version)

chars = [chr(c) for c in range(0x110000) if not 0xD800 <= c <= 0xDFFF]
chars = [c for c in chars if not c.isspace() and c not in wordfreq.PUNCTUATION]
expected = Counter(c.lower() for c in chars)

with tempfile.TemporaryDirectory() as tmp:
    path = Path(tmp) / "all.txt"
    path.write_text(" ".join(chars), encoding="utf-8")
    out = subprocess.run(
        [binary, str(path), "--top", "9" * 30, "--json"], capture_output=True, check=True
    ).stdout
data = json.loads(out)
actual = Counter({item["word"]: item["count"] for item in data["top"]})
# 입력 전체가 기준 구현의 토큰화와 같은지도 본다
py_actual = Counter(wordfreq.tokenize(" ".join(chars)))
assert py_actual == expected, "python tokenize differs from per-char lower"

missing = expected - actual
extra = actual - expected
print("expected-only words:", len(missing), "rust-only words:", len(extra))
for w in sorted(missing):
    print("  python-only", " ".join(f"U+{ord(c):04X}" for c in w))
for w in sorted(extra):
    print("  rust-only  ", " ".join(f"U+{ord(c):04X}" for c in w))
