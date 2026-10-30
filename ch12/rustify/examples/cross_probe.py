"""Codex 노트가 찾은 가장자리 항목을 여러 실행 결과에 똑같이 시험한다: cross_probe.py <작업 폴더>..."""
import os
import subprocess
import sys
import tempfile
from pathlib import Path


def run(ws: Path, python: bool, args: list, stdin: bytes = b"# A\n") -> tuple:
    cmd = [str(ws / ".venv/bin/python"), str(ws / "python_src/mdtoc.py")] if python else [str(ws / "rust_app/target/release/mdtoc")]
    p = subprocess.run(cmd + args, input=stdin, capture_output=True)
    return p.returncode, p.stdout, p.stderr


def probes(tmp: Path) -> list:
    raw = os.fsencode(str(tmp)) + b"/name_\x80"
    Path(os.fsdecode(raw)).write_bytes(b"# raw\n")
    return [
        ("help: -hx", ["-hx"], "code"),
        ("help: -hh", ["-hh"], "code"),
        ("help: --bogus -h", ["--bogus", "-h"], "code"),
        ("help: --js --help", ["--js", "--help"], "code"),
        ("int: 0*4300+1", ["--min-level", "0" * 4300 + "1"], "code"),
        ("int: arabic 0*4300+1", ["--min-level", "\u0660" * 4300 + "1"], "code"),
        ("int: 0*4298+1", ["--min-level", "0" * 4298 + "1"], "all"),
        ("file: LF in missing name", ["no\nsuch.md"], "all"),
        ("file: raw byte name", [raw], "all"),
        ("file: missing raw byte name", [b"missing_\xff"], "all"),
    ]


def main() -> None:
    with tempfile.TemporaryDirectory() as t:
        cases = probes(Path(t))
        for ws in map(Path, sys.argv[1:]):
            print(f"##### {ws.name}")
            for name, args, mode in cases:
                py, rs = run(ws, True, args), run(ws, False, args)
                same = py[0] == rs[0] and (mode == "code" or py[1:] == rs[1:])
                print(f"{'OK  ' if same else 'DIFF'} {name}: python {py[0]}, rust {rs[0]}"
                      + ("" if same or mode == "code" else f" | stderr py={py[2][-80:]!r} rs={rs[2][-80:]!r}"))


if __name__ == "__main__":
    main()
