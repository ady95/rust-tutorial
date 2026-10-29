"""인자 조합을 기준 구현의 argparse 와 비교한다(종료 코드, stdout, 오류 시 stderr 비어 있음 여부).

    python3 verify/args_diff.py [깊이]

토큰의 길이 깊이 이하 조합을 전부 시험한다. 작업 폴더로 쓰는 임시 폴더에 파일 a, b 를 두어
파일 이름이 a, b 이면 읽히고 그 밖의 이름은 읽기 오류(종료 코드 1)가 되게 한다.
"""
import contextlib
import io
import itertools
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "python_src"))
import mdtoc  # noqa: E402

RUST = ROOT / "rust_app" / "target" / "release" / "mdtoc"
DOC = "# A\n## B\n### C\n## B\n"
TOKENS = ["a", "b", "-", "--", "--json", "--numbered", "--min-level", "--max-level", "2", "7",
          "-h", "-5", "--min-level=3", "--js", "-x", "--json=1", "-hx", "x y", "--max-level=0", "٣"]


def expected(argv: list[str]) -> tuple[int, bytes, bool]:
    err = io.StringIO()
    out = io.StringIO()
    try:
        with contextlib.redirect_stderr(err), contextlib.redirect_stdout(out):
            args = mdtoc.parse_args(argv)
    except SystemExit as e:
        code = e.code if isinstance(e.code, int) else 1
        return code, b"" if code else b"<help>", bool(err.getvalue())
    if args.file not in ("-", "a", "b"):
        return 1, b"", True
    entries = mdtoc.build(DOC, args.min_level, args.max_level)
    if args.json:
        text = json.dumps(entries, ensure_ascii=False) + "\n"
    elif args.numbered:
        text = mdtoc.render_numbered(entries, args.min_level)
    else:
        text = mdtoc.render(entries, args.min_level)
    return 0, text.encode(), False


def main() -> int:
    depth = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    bad = total = 0
    with tempfile.TemporaryDirectory() as tmp:
        for name in "ab":
            Path(tmp, name).write_text(DOC)
        for n in range(depth + 1):
            for argv in itertools.product(TOKENS, repeat=n):
                argv = list(argv)
                want = expected(argv)
                p = subprocess.run([str(RUST), *argv], input=DOC.encode(), capture_output=True, cwd=tmp)
                out = p.stdout
                if want[1] == b"<help>":
                    # 도움말 내용은 비교 안 함: 비어 있지 않기만 확인
                    out = b"<help>" if out else b""
                got = (p.returncode, out, bool(p.stderr))
                total += 1
                if got != want:
                    bad += 1
                    if bad <= 20:
                        print("MISMATCH", argv, want, got)
    print(f"{total} arg lists, {bad} mismatches")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
