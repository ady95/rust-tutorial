"""cases.json 으로는 표현하기 어려운 오류·환경·부작용 시나리오를 기준 구현과 Rust 구현에 똑같이 실행해 비교한다.

07-3의 scenarios.py 를 계약 2판에 맞춘 것이다.
- 인자 오류: 종료 코드가 같고 stderr 가 비어 있지 않으면 같음 (계약 4절)
- 출력 실패(파이프를 일찍 닫음, 디스크 가득 참): Rust 종료 코드가 0이 아니고, 멈추지(101) 않고,
  시그널로 끝나지 않으면 같음. stdout·stderr 는 비교하지 않음 (계약 5절)
- 그 밖: 종료 코드, stdout, stderr 모두 바이트 단위로 같아야 함
- 모든 시나리오: 실행 전후 작업 폴더의 파일 목록과 크기가 같아야 함(부작용 없음)

Linux 전용(권한·/dev/full·바이트 파일 이름). 일반 사용자로 실행해야 권한 시나리오가 의미 있다.

사용법 (프로젝트 루트에서): python3 automation/scenarios.py [--rust rust_app/target/release/wordfreq]
종료 코드: 0 = 모두 같음, 1 = 다름, 2 = Rust 실행 파일 없음, 4 = Linux 가 아니어서 건너뜀
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REFERENCE = ROOT / "python_src" / "wordfreq.py"


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


# (이름, 인자, stdout 처리, 비교 규칙)
SCENARIOS = [
    ("missing-file", [b"nope.txt"], "pipe", "exact"),
    ("directory", [b"adir"], "pipe", "exact"),
    ("permission-denied", [b"secret.txt"], "pipe", "exact"),
    ("non-utf8-filename", [b"bad\xffname.txt"], "pipe", "exact"),
    ("non-utf8-missing", [b"gone\xff.txt"], "pipe", "exact"),
    ("non-utf8-missing-2", [b"x\xe2\x82y\xf0\x9f.txt"], "pipe", "exact"),
    ("dash-filename", [b"-"], "pipe", "exact"),
    ("double-dash", [b"--", b"basic.txt"], "pipe", "exact"),
    ("top-repeated", [b"basic.txt", b"--top", b"1", b"--top", b"2"], "pipe", "exact"),
    ("top-fullwidth", [b"basic.txt", b"--top", "２".encode()], "pipe", "usage"),
    ("top-huge", [b"basic.txt", b"--top", b"1" + b"0" * 30], "pipe", "exact"),
    ("top-zero", [b"basic.txt", b"--top", b"0"], "pipe", "usage"),
    ("top-equals", [b"basic.txt", b"--top=1"], "pipe", "exact"),
    ("closed-pipe", [b"many.txt", b"--top", b"1000000"], "close-early", "output-failure"),
    ("disk-full", [b"basic.txt"], "dev-full", "output-failure"),
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


def judge(rule: str, py: tuple[int, bytes, bytes], rs: tuple[int, bytes, bytes]) -> list[str]:
    problems = []
    if rule == "output-failure":
        if rs[0] == 0:
            problems.append("exit code: rust=0, 출력 실패인데 성공으로 끝남")
        elif rs[0] == 101:
            problems.append("exit code: rust=101 (panic)")
        elif rs[0] < 0:
            problems.append(f"exit code: rust={rs[0]} (시그널로 종료)")
        return problems
    if py[0] != rs[0]:
        problems.append(f"exit code: python={py[0]} rust={rs[0]}")
    if rule == "usage":
        if not rs[2]:
            problems.append("stderr: rust printed nothing")
        return problems
    if py[1] != rs[1]:
        problems.append(f"stdout: python={short(py[1])} rust={short(rs[1])}")
    if py[2] != rs[2]:
        problems.append(f"stderr: python={short(py[2])} rust={short(rs[2])}")
    return problems


def short(data: bytes) -> str:
    text = repr(data)
    return text if len(text) <= 90 else text[:87] + "..."


def main() -> int:
    parser = argparse.ArgumentParser(description="Run error and environment scenarios.")
    parser.add_argument("--rust", type=Path, default=ROOT / "rust_app" / "target" / "release" / "wordfreq")
    parser.add_argument("--report", type=Path, help="write JSON result to this file")
    args = parser.parse_args()
    if not sys.platform.startswith("linux"):
        print("scenarios: Linux only, skipped")
        return 4
    if not args.rust.exists():
        print(f"Rust binary not found: {args.rust}", file=sys.stderr)
        return 2
    binary = args.rust.resolve()
    results = []
    for name, cmd_args, mode, rule in SCENARIOS:
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            prepare(work)
            before = snapshot(work)
            py = run([os.fsencode(sys.executable), os.fsencode(REFERENCE), *cmd_args], work, mode)
            rs = run([os.fsencode(binary), *cmd_args], work, mode)
            problems = judge(rule, py, rs)
            if snapshot(work) != before:
                problems.append("side effect: files in the working directory changed")
            (work / "secret.txt").chmod(0o600)
        results.append({"name": name, "ok": not problems, "problems": problems})
        print(f"{'OK  ' if not problems else 'FAIL'} {name}")
        for problem in problems:
            print(f"     {problem}")
    passed = sum(r["ok"] for r in results)
    print(f"\n{passed}/{len(results)} scenarios match")
    if args.report:
        args.report.write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
