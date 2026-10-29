"""R5/R6/R7/R9/R10: 경로 정규화, 읽기 오류 분류, UTF-8 아닌 파일 이름, 출력 실패/닫힌 fd 비교."""
from __future__ import annotations

import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from x_lib import ENV, PY, REF, ROOT, RS, both, judge, parallel  # noqa: E402

FS = os.path.join(ROOT, "verify", "x_work_fs")
FSB = os.fsencode(FS)


def setup():
    os.makedirs(FS, exist_ok=True)

    def w(name: bytes, data: bytes, mode=None):
        p = os.path.join(FSB, name)
        if os.path.lexists(p):
            os.chmod(p, 0o600) if not os.path.islink(p) else None
            os.unlink(p)
        with open(p, "wb") as fp:
            fp.write(data)
        if mode is not None:
            os.chmod(p, mode)

    def link(name: bytes, target: bytes):
        p = os.path.join(FSB, name)
        if os.path.lexists(p):
            os.unlink(p)
        os.symlink(target, p)

    w(b"basic.txt", b"the cat the hat\n")
    w(b"secret.txt", b"hidden\n", 0)
    w(b"bom.txt", b"\xef\xbb\xbfhello hello\n")
    w(b"bom_only.txt", b"\xef\xbb\xbf")
    w(b"crlf.txt", b"A\r\nb\rc\r\n\r\n")
    w(b"nul.txt", b"a\x00b a\x00b \x00\n")
    w(b"bad_utf8_tail.txt", b"ok ok \xe2\x82")
    w(b"surrogate.txt", b"a \xed\xa0\x80 b")
    w(b"overlong.txt", b"a \xc0\xaf b")
    w(b"above_max.txt", b"a \xf4\x90\x80\x80 b")
    w(b"nonchar.txt", "a ￿ \U0010ffff ￾ b".encode())
    w(b"cr_only.txt", b"\r\r\r")
    w(b"bad\xffname.txt", b"byte name\n")
    if not os.path.isdir(os.path.join(FSB, b"adir")):
        os.mkdir(os.path.join(FSB, b"adir"))
    locked = os.path.join(FSB, b"locked")
    if not os.path.isdir(locked):
        os.mkdir(locked)
    os.chmod(locked, 0o700)
    with open(os.path.join(locked, b"in.txt"), "wb") as fp:
        fp.write(b"x\n")
    os.chmod(locked, 0)
    link(b"loop1", b"loop2")
    link(b"loop2", b"loop1")
    link(b"dangling", b"nowhere.txt")
    link(b"flink", b"basic.txt")
    link(b"dlink", b"adir")
    link(b"selfloop", b"selfloop/x")


PATH_CASES = [
    b"basic.txt", b"basic.txt/", b"basic.txt/.", b"basic.txt//", b"basic.txt/./", b"./basic.txt",
    b".//basic.txt", b"adir/../basic.txt", b"basic.txt/..", b"basic.txt/x", b"basic.txt/./x",
    b"", b".", b"./", b"..", b"../", b"/", b"//", b"///", b"adir", b"adir/", b"adir/.",
    b"nope.txt", b"nope.txt/", b"nope.txt/.", b"nope/x", b"basic.txt/nope/..",
    b"secret.txt", b"locked/in.txt", b"locked/", b"locked/nope",
    b"loop1", b"loop1/", b"selfloop", b"dangling", b"dangling/", b"flink", b"flink/", b"flink/.",
    b"dlink", b"dlink/", b"a" * 255, b"a" * 256, b"a" * 300, b"a" * 300 + b"/x",
    (b"adir/" * 1000) + b"x", (b"./" * 3000) + b"basic.txt", (b"d/" * 2100),
    b"bom.txt", b"bom_only.txt", b"crlf.txt", b"nul.txt", b"bad_utf8_tail.txt", b"surrogate.txt",
    b"overlong.txt", b"above_max.txt", b"nonchar.txt", b"cr_only.txt", b"bad\xffname.txt",
    b"bad\xffname.txt/", b"/dev/null", b"/dev/null/", b"/dev/zero/x", b"/proc/self/nope",
    b"\xff", b"\xff/", b"-", b"~", b"$HOME", b"*", b"basic.txt\n", b" basic.txt", b"basic.txt ",
    b"\\basic.txt", b"basic.txt:", b"BASIC.TXT",
]


def path_cases():
    out = []
    for p in PATH_CASES:
        args_list = [[p], [p, b"--json"]]
        if p.startswith(b"-"):
            args_list = [[b"--", p]]
        for args in args_list:
            py, rs = both(args, cwd=FS)
            why = judge(py, rs)
            out.append((args, why, py, rs))
    return out


def bad_name_seqs():
    seqs = [bytes([b]) for b in range(0x80, 0x100)]
    seconds = [0x41, 0x7F, 0x80, 0x8F, 0x90, 0x9F, 0xA0, 0xBF, 0xC0, 0xC2, 0xE0, 0xF0, 0xFF]
    for lead in range(0x80, 0x100):
        for s in seconds:
            seqs.append(bytes([lead, s]))
    for lead in range(0xE0, 0xF5):
        for s in range(0x80, 0xC0):
            for t in (0x41, 0x80, 0xBF, 0xC0):
                seqs.append(bytes([lead, s, t]))
    for lead in range(0xF0, 0xF5):
        for s in range(0x80, 0xC0):
            for t in (0x80, 0xBF):
                for u in (0x41, 0x80):
                    seqs.append(bytes([lead, s, t, u]))
    return seqs


def name_check(seq):
    out = []
    for name in (b"n" + seq + b"z", b"n" + seq):
        py, rs = both([name], cwd=FS)
        why = judge(py, rs)
        if why:
            out.append(([name], why, py, rs))
    return out


def run_fd(binargs, how, cwd=FS):
    """how: closed-pipe, dev-full, close1, close2"""
    kw = {}
    if how == "closed-pipe":
        r, w = os.pipe()
        os.close(r)
        kw["stdout"] = w
        kw["stderr"] = subprocess.PIPE
    elif how == "dev-full":
        kw["stdout"] = open("/dev/full", "wb")
        kw["stderr"] = subprocess.PIPE
    elif how == "close1":
        kw["stdout"] = subprocess.PIPE
        kw["stderr"] = subprocess.PIPE
        kw["preexec_fn"] = lambda: os.close(1)
    elif how == "close2":
        kw["stdout"] = subprocess.PIPE
        kw["stderr"] = subprocess.PIPE
        kw["preexec_fn"] = lambda: os.close(2)
    p = subprocess.run(binargs, cwd=cwd, env=ENV, stdin=subprocess.DEVNULL, timeout=60, **kw)
    if how == "closed-pipe":
        os.close(kw["stdout"])
    if how == "dev-full":
        kw["stdout"].close()
    return p.returncode, p.stdout or b"", p.stderr or b""


def io_cases():
    out = []
    big = os.path.join(FSB, b"many.txt")
    with open(big, "wb") as fp:
        fp.write(" ".join(f"w{i}" for i in range(50000)).encode())
    arglists = [[b"basic.txt"], [b"basic.txt", b"--json"], [b"many.txt", b"--top", b"999999"],
                [b"-h"], [b"--help"], [b"basic.txt", b"-h"], [b"nope.txt"], [b"basic.txt", b"--bogus"],
                [b"adir"]]
    for how in ("closed-pipe", "dev-full", "close1", "close2"):
        for a in arglists:
            py = run_fd([os.fsencode(PY), os.fsencode(REF), *a], how)
            rs = run_fd([os.fsencode(RS), *a], how)
            out.append((how, a, py, rs))
    return out


def main():
    setup()
    bad = []
    pc = path_cases()
    print("path cases", len(pc))
    for args, why, py, rs in pc:
        if why:
            bad.append((args, why, py, rs))
            print("DIFF", repr(args)[:120], why, "\n   py", repr(py)[:300], "\n   rs", repr(rs)[:300])
    seqs = bad_name_seqs()
    res = parallel(name_check, seqs, workers=16)
    n = sum(1 for _ in seqs) * 2
    nb = [x for r in res for x in r]
    print("bad-utf8 name cases", n, "diffs", len(nb))
    for args, why, py, rs in nb[:20]:
        print("DIFF", repr(args), why, "\n   py", py, "\n   rs", rs)
    print("--- io cases (contract 5: output failure must be nonzero, no panic/signal) ---")
    for how, a, py, rs in io_cases():
        flag = ""
        if py[0] != rs[0]:
            flag = "  <== exit differs"
        if rs[0] in (0,) and how in ("closed-pipe", "dev-full") and a not in ([b"nope.txt"], [b"basic.txt", b"--bogus"], [b"adir"]):
            flag += "  <== rust 0 on output failure"
        if rs[0] < 0 or rs[0] == 101:
            flag += "  <== rust panic/signal"
        print(how, a, "py", py[0], repr(py[1][:60]), repr(py[2][-160:]), "| rs", rs[0], repr(rs[1][:60]), repr(rs[2][-160:]), flag)


if __name__ == "__main__":
    main()
