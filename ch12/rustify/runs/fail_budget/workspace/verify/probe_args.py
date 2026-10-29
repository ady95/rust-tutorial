import contextlib
import io
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "python_src"))
import mdtoc

CASES = [
    ["--json", "f"], ["f", "--json"], ["--min-level", "2", "f"], ["f", "--json", "g"],
    ["--json", "--", "f"], ["-5"], ["--min-level=3", "f"], ["--min-level", " 3 "],
    ["--min-level", "-1"], ["--bogus", "-h"], ["--json", "f", "--numbered", "g"],
    ["--min-level", "+2"], ["--min-level", "٣"], ["--", "-x"], ["-", "--json"],
    ["a b"], ["-a b"], ["--max-level", "3", "--max-level", "4"], ["-hx"], ["--json=1"],
]
for a in CASES:
    err = io.StringIO()
    out = io.StringIO()
    try:
        with contextlib.redirect_stderr(err), contextlib.redirect_stdout(out):
            ns = mdtoc.parse_args(a)
        print(a, "ok", ns.file, ns.min_level, ns.max_level)
    except SystemExit as e:
        print(a, "exit", e.code)
