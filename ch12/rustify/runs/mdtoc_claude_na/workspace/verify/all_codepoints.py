"""모든 코드 포인트에 대해 Python 기준 구현과 Rust 결과를 비교한다 (앵커·제목 정리·인자 해석)."""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "python_src"))
import json  # noqa: E402

import mdtoc  # noqa: E402

BIN = ROOT / "rust_app" / "target" / "release" / "mdtoc"


def run(args, data=b""):
    p = subprocess.run([str(BIN), *args], input=data, capture_output=True)
    return p.returncode, p.stdout


def expected(text):
    return json.dumps(mdtoc.build(text, 1, 6), ensure_ascii=False) + "\n"


def check_text(text, label):
    code, out = run(["--json"], text.encode("utf-8"))
    want = expected(text)
    if code != 0 or out.decode("utf-8") != want:
        print("MISMATCH", label)
        print(" want", want[:300].encode("unicode_escape"))
        print(" got ", out[:300].decode("utf-8", "replace").encode("unicode_escape"))
        return False
    return True


def main():
    bad = 0
    cps = [c for c in range(0x110000) if not 0xD800 <= c < 0xE000]
    templates = ["# {c}\n", "# A{c}Σ\n", "# {c}Σ\n", "# Σ{c}a\n", "# a{c}Σ{c}\n",
                 "## x {c} ##\n", "# x{c}#\n", "# x {c}#\n", "#{c}x\n", "```{c}\n# in\n```\n# {c}\n"]
    for t in templates:
        for i in range(0, len(cps), 4000):
            text = "".join(t.format(c=chr(c)) for c in cps[i:i + 4000])
            if not check_text(text, f"{t!r} @ {cps[i]:X}"):
                bad += 1
    # 인자 해석: 종료 코드를 비교한다 (stdout 은 정상일 때만)
    md = b"# A\n## B\n### C\n"
    cases = [[], ["--json"], ["--numbered"], ["--min-level", "2"], ["--min-level=2", "--max-level", "3"],
             ["--min-level", "٣"], ["--min-level", " 2 "], ["--min-level", "+2"], ["--min-level", "1_0"],
             ["--min-level", "0"], ["--min-level", "7"], ["--min-level"], ["--min-level", "--json"],
             ["--min-level", "-1"], ["--min-level", "3", "--max-level", "2"], ["--js"], ["--bogus"],
             ["--bogus", "--help"], ["--help"], ["-h"], ["-hh"], ["-hx"], ["-h=x"], ["-hxh"], ["-xh"], ["-hx", "--bogus"],["--json=1"], ["--help=1"],
             ["-"], ["a", "b"], ["--", "-"], ["--", "-x"], ["-1"], ["-x y"], ["--min-level", "2", "--"],
             ["--min-level", "9", "--help"], ["--help", "--min-level", "9"], ["--max-level", "03"],
             ["--max-level", "1_"], ["--max-level", "_1"], ["--max-level", "99999999999999999999"]]
    for args in cases:
        pc = subprocess.run([sys.executable, str(ROOT / "python_src" / "mdtoc.py"), *args], input=md,
                            capture_output=True)
        rc, rout = run(args, md)
        same = pc.returncode == rc and (pc.returncode != 0 or pc.stdout.startswith(b"usage") or
                                        pc.stdout == rout)
        if rc == 2 and not pc.stderr or (rc == 2) != (pc.returncode == 2):
            same = False
        if not same:
            bad += 1
            print("ARG MISMATCH", args, "py", pc.returncode, pc.stdout[:60], "rust", rc, rout[:60])
    print("FAIL" if bad else "ALL OK", bad)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
