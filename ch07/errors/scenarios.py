"""cases.json 으로는 표현하기 어려운 오류·환경·부작용 시나리오를 Python 기준 구현과 Rust 구현에 똑같이 실행해 비교한다 (07-3).

비교: 종료 코드, stdout(바이트), stderr(바이트, usage 시나리오는 "비어 있지 않음"만), 작업 폴더의 파일 변화(부작용)
Linux 전용(권한·/dev/full·바이트 파일 이름). 일반 사용자로 실행해야 권한 시나리오가 의미 있다.

사용법 (ch07/errors 에서): python3 scenarios.py <Rust 실행 파일> [...]
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REFERENCE = ROOT / "ch05" / "wordfreq" / "python_src" / "wordfreq.py"


def prepare(work: Path) -> None:
    (work / "basic.txt").write_text("the cat the hat\n", encoding="utf-8")
    (work / "secret.txt").write_text("hidden\n", encoding="utf-8")
    (work / "secret.txt").chmod(0)
    (work / "adir").mkdir()
    (work / "-").write_text("dash file\n", encoding="utf-8")
    # 파일 이름이 UTF-8 이 아닌 바이트(0xFF)인 파일. Linux 는 파일 이름을 바이트로 다룬다
    with open(os.path.join(os.fsencode(work), b"bad\xffname.txt"), "w", encoding="utf-8") as fp:
        fp.write("byte name\n")
    # 파이프 버퍼(보통 64KB)를 넘는 출력을 만드는 입력
    (work / "many.txt").write_text(" ".join(f"w{i}" for i in range(200_000)) + "\n", encoding="utf-8")


# (이름, 인자, stdout 처리, usage 여부)
SCENARIOS = [
    ("missing-file", [b"nope.txt"], "pipe", False),
    ("directory", [b"adir"], "pipe", False),
    ("permission-denied", [b"secret.txt"], "pipe", False),
    ("non-utf8-filename", [b"bad\xffname.txt"], "pipe", False),
    ("non-utf8-missing", [b"gone\xff.txt"], "pipe", False),
    ("dash-filename", [b"-"], "pipe", False),
    ("double-dash", [b"--", b"basic.txt"], "pipe", False),
    ("top-repeated", [b"basic.txt", b"--top", b"1", b"--top", b"2"], "pipe", False),
    ("top-fullwidth", [b"basic.txt", b"--top", "２".encode()], "pipe", False),
    ("top-huge", [b"basic.txt", b"--top", b"1" + b"0" * 30], "pipe", False),
    ("top-zero", [b"basic.txt", b"--top", b"0"], "pipe", True),
    ("top-equals", [b"basic.txt", b"--top=1"], "pipe", False),
    ("closed-pipe", [b"many.txt", b"--top", b"1000000"], "close-early", False),
    ("disk-full", [b"basic.txt"], "dev-full", False),
]


def snapshot(work: Path) -> dict[bytes, int]:
    result = {}
    for dirpath, _, files in os.walk(os.fsencode(work)):
        for name in files:
            full = os.path.join(dirpath, name)
            result[os.path.relpath(full, os.fsencode(work))] = os.lstat(full).st_size
    return result


def run(cmd: list[bytes], work: Path, mode: str) -> tuple[int, bytes, bytes]:
    if mode == "pipe":
        proc = subprocess.run(cmd, cwd=work, capture_output=True, timeout=60)
        return proc.returncode, proc.stdout, proc.stderr
    if mode == "dev-full":
        with open("/dev/full", "wb") as full:
            proc = subprocess.run(cmd, cwd=work, stdout=full, stderr=subprocess.PIPE, timeout=60)
        return proc.returncode, b"", proc.stderr
    # close-early: 출력의 첫 1바이트만 읽고 파이프를 닫는다 (head -c 1 과 같은 상황)
    proc = subprocess.Popen(cmd, cwd=work, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    first = proc.stdout.read(1)
    proc.stdout.close()
    err = proc.stderr.read()
    return proc.wait(timeout=60), first, err


def short(data: bytes) -> str:
    text = data.decode("utf-8", "backslashreplace").replace("\n", "⏎")
    return text if len(text) <= 90 else text[:87] + "..."


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    binaries = [Path(p).resolve() for p in sys.argv[1:]]
    results = []
    for name, args, mode, usage in SCENARIOS:
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            prepare(work)
            before = snapshot(work)
            py = run([os.fsencode(sys.executable), os.fsencode(REFERENCE), *args], work, mode)
            py_after = snapshot(work)
            row = {"scenario": name, "python": {"exit": py[0], "stdout": short(py[1]), "stderr": short(py[2]),
                                                "side_effect": py_after != before}}
            for binary in binaries:
                rs = run([os.fsencode(binary), *args], work, mode)
                rs_after = snapshot(work)
                same_exit = rs[0] == py[0]
                same_out = rs[1] == py[1]
                same_err = bool(rs[2]) if usage else rs[2] == py[2]
                row[binary.name] = {"exit": rs[0], "same": same_exit and same_out and same_err,
                                    "same_exit": same_exit, "same_stdout": same_out, "same_stderr": same_err,
                                    "stderr": short(rs[2]), "side_effect": rs_after != py_after}
            (work / "secret.txt").chmod(0o600)
        results.append(row)
        marks = " ".join(f"{b.name}={'same' if row[b.name]['same'] else 'DIFF'}" for b in binaries)
        print(f"{name:<20} python exit={py[0]:<4} {marks}")
    out = Path(__file__).resolve().parent / "scenario_results.json"
    out.write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
