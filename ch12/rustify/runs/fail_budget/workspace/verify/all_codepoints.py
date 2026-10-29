"""모든 코드 포인트(제목 안, 소문자화 전후 앵커)와 인자 해석을 Python 기준 구현과 비교한다."""
import json
import os
import subprocess
import sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, os.path.join(ROOT, "python_src"))
import mdtoc  # noqa: E402

BIN = os.path.join(ROOT, "rust_app", "target", "release", "mdtoc")
fail = 0

# 1) 코드 포인트마다 "# a<c>b<c>" 제목. 줄 경계 글자는 제외(제목이 갈라짐)
lines = []
for c in range(0x110000):
    if 0xD800 <= c <= 0xDFFF:
        continue
    ch = chr(c)
    if len(("x" + ch + "x").splitlines()) != 1:
        continue
    lines.append(f"# a{ch}b{ch}Σ{ch}")
text = "\n".join(lines) + "\n"
want = json.dumps(mdtoc.build(text, 1, 6), ensure_ascii=False) + "\n"
got = subprocess.run([BIN, "--json"], input=text.encode(), capture_output=True).stdout.decode()
if want != got:
    fail += 1
    print("FAIL codepoints")
else:
    print("OK codepoints", len(lines))

# 2) 인자 해석
CASES = [
    ["--json", "f"], ["f", "--json"], ["--min-level", "2", "f"], ["f", "--json", "g"],
    ["--json", "--", "f"], ["-5"], ["--min-level=3", "f"], ["--min-level", " 3 "],
    ["--min-level", "-1"], ["--bogus", "-h"], ["--json", "f", "--numbered", "g"],
    ["--min-level", "+2"], ["--min-level", "٣"], ["--", "-x"], ["-", "--json"],
    ["a b"], ["-a b"], ["--max-level", "3", "--max-level", "4"], ["-hx"], ["--json=1"],
    ["--min-level"], ["--min-level", "1_1"], ["--min-level", "0"], ["--min-level", "4", "--max-level", "3"],
    ["-x"], ["--js"], ["--min-level", "--json"], ["--min-level=", "f"],
]
for a in CASES:
    import contextlib
    import io

    try:
        with contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(io.StringIO()):
            ns = mdtoc.parse_args(a)
        # 파일은 없는 경로로 읽기 실패(1)가 되므로 인자 해석 성공은 종료 코드 1 또는 0
        py = "ok"
    except SystemExit as e:
        py = f"exit{e.code}"
    r = subprocess.run([BIN, *a], input=b"", capture_output=True, cwd=ROOT)
    rs = {0: "ok" if py != "exit0" else "exit0", 1: "ok", 2: "exit2"}[r.returncode]
    if py == "exit0":
        rs = "exit0" if r.returncode == 0 else f"exit{r.returncode}"
    if py != rs:
        fail += 1
        print("FAIL args", a, py, rs)
print("args checked", len(CASES))
sys.exit(1 if fail else 0)
