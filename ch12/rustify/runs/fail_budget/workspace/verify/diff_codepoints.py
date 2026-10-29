"""all_codepoints.py 가 실패할 때 어느 코드 포인트가 다른지 보여 준다."""
import json
import os
import subprocess
import sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, os.path.join(ROOT, "python_src"))
import mdtoc  # noqa: E402

BIN = os.path.join(ROOT, "rust_app", "target", "release", "mdtoc")
chars = [chr(c) for c in range(0x110000) if not 0xD800 <= c <= 0xDFFF and len(("x" + chr(c) + "x").splitlines()) == 1]
# 중복 앵커 영향을 피하려고 코드 포인트마다 따로 나눠 한 번에 실행하되 문서를 쪼갠다
shown = 0
for i in range(0, len(chars), 2000):
    chunk = chars[i : i + 2000]
    text = "".join(f"# a{c}b{c}Σ{c}\n" for c in chunk)
    want = json.loads(json.dumps(mdtoc.build(text, 1, 6), ensure_ascii=False))
    got = json.loads(subprocess.run([BIN, "--json"], input=text.encode(), capture_output=True).stdout.decode())
    if len(want) != len(got):
        print("length differs", i, len(want), len(got))
    for c, w, g in zip(chunk, want, got):
        if w != g and shown < 15:
            shown += 1
            print(hex(ord(c)), w, g)
print("done")
