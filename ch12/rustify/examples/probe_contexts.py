"""fail_budget 의 Rust 와 기준 구현이 어느 맥락·글자에서 다른지 찾는다. 작업 폴더에서: .venv/bin/python probe_diff.py"""
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

ROOT = Path.cwd()
sys.path.insert(0, str(ROOT / "python_src"))
sys.path.insert(0, str(ROOT / "xverify"))
import mdtoc  # noqa: E402
from exhaustive_codepoints import CONTEXTS  # noqa: E402

RUST = ROOT / "rust_app" / "target" / "release" / "mdtoc"
by_ctx = Counter()
examples = {}
cps = [c for c in range(0x110000) if not 0xD800 <= c < 0xE000]
for ci, ctx in enumerate(CONTEXTS):
    # 맥락마다 글자 1,000개씩 묶어 한 문서로 비교하고, 다르면 글자 하나씩 다시 본다
    for i in range(0, len(cps), 1000):
        group = cps[i:i + 1000]
        text = "\n".join(ctx.replace("{c}", chr(c)) for c in group) + "\n"
        want = (json.dumps(mdtoc.build(text, 1, 6), ensure_ascii=False) + "\n").encode()
        got = subprocess.run([str(RUST), "--json"], input=text.encode(), capture_output=True).stdout
        if got == want:
            continue
        for c in group:
            t = ctx.replace("{c}", chr(c)) + "\n"
            w = (json.dumps(mdtoc.build(t, 1, 6), ensure_ascii=False) + "\n").encode()
            g = subprocess.run([str(RUST), "--json"], input=t.encode(), capture_output=True).stdout
            if g != w:
                by_ctx[ci] += 1
                examples.setdefault(ci, []).append((hex(c), w.decode()[:120], g.decode("utf-8", "replace")[:120]))
for ci, n in sorted(by_ctx.items()):
    print(f"context {ci} {CONTEXTS[ci]!r}: {n} code points")
    for ex in examples[ci][:3]:
        print("   ", ex)
