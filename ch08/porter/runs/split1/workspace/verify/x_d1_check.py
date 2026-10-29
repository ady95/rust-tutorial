import os, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUST = [os.path.join(ROOT, "rust_app/target/release/wordfreq")]
PY = [sys.executable, os.path.join(ROOT, "python_src/wordfreq.py")]
FIX = b"tests/fixtures/basic.txt"
CASES = [[b"-h"], [b"--help"], [FIX, b"-h"], [FIX], [FIX, b"--json"]]


def run_closed_pipe(cmd, args):
    r, w = os.pipe()
    os.close(r)
    p = subprocess.Popen(cmd + args, stdout=w, stderr=subprocess.PIPE, cwd=ROOT)
    os.close(w)
    _, err = p.communicate(timeout=20)
    return p.returncode, err


def run_full(cmd, args):
    with open("/dev/full", "wb") as f:
        p = subprocess.run(cmd + args, stdout=f, stderr=subprocess.PIPE, cwd=ROOT, timeout=20)
    return p.returncode, p.stderr


def run_ok(cmd, args):
    p = subprocess.run(cmd + args, capture_output=True, cwd=ROOT, timeout=20)
    return p.returncode, p.stdout, p.stderr


bad = 0
for args in CASES:
    for name, fn in (("closed_pipe", run_closed_pipe), ("dev_full", run_full)):
        rc_r, er_r = fn(RUST, args)
        rc_p, er_p = fn(PY, args)
        ok = rc_r == rc_p and b"panick" not in er_r
        bad += not ok
        print(f"{'OK ' if ok else 'DIFF'} {args!r} {name}: rust={rc_r} py={rc_p}"
              + ("" if er_r == er_p else f" stderr_differs rust={er_r[:120]!r} py={er_p[:120]!r}"))
    rc_r, o_r, e_r = run_ok(RUST, args)
    rc_p, o_p, e_p = run_ok(PY, args)
    ok = rc_r == rc_p and o_r == o_p and e_r == e_p
    bad += not ok
    print(f"{'OK ' if ok else 'DIFF'} {args!r} normal: rust={rc_r} py={rc_p} stdout_eq={o_r == o_p} stderr_eq={e_r == e_p}")
print("mismatches:", bad)
