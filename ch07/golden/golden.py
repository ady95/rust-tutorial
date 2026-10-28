"""Golden test: Python 기준 구현의 출력을 파일로 저장해 두고, Rust 구현을 그 파일과 비교한다 (07-1).

    python3 golden.py record                 # 기준 구현을 실행해 goldens/ 에 저장
    python3 golden.py check --rust <실행 파일>  # Rust 만 실행해 저장된 출력과 비교

- 케이스: ch05/wordfreq/tests/cases.json(17개) + extra_cases.json
- 모든 명령은 ch05/wordfreq 를 작업 폴더로 실행한다(오류 메시지의 파일 경로가 같아야 하므로)
- 비교 규칙은 compare.py 와 같다: stdout·stderr 바이트, 종료 코드. usage_error 케이스는 종료 코드와
  "stderr 가 비어 있지 않음"만 본다
- hash_only 케이스는 출력이 커서 SHA-256 만 저장한다. 다르다는 것은 알 수 있지만 어디가 다른지는 보여 줄 수 없다
- 기록 당시의 기준 구현·입력 파일 해시를 manifest 에 남긴다. 둘 중 하나라도 바뀌면 check 는 비교하지 않고
  "다시 기록하고 검토하라"며 종료 코드 3 으로 끝난다(낡은 기준 출력과 비교하는 사고를 막는다)

종료 코드: 0 = 모두 일치, 1 = 불일치, 3 = 기준 출력이 낡음
"""

import argparse
import hashlib
import json
import platform
import subprocess
import sys
import time
import unicodedata
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[1] / "ch05" / "wordfreq"
REFERENCE = PROJECT / "python_src" / "wordfreq.py"
GOLDENS = HERE / "goldens"
CASE_FILES = [PROJECT / "tests" / "cases.json", HERE / "extra_cases.json"]
INLINE_LIMIT = 64 * 1024


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_cases() -> list[dict]:
    return [case for path in CASE_FILES for case in json.loads(path.read_text(encoding="utf-8"))]


def input_hashes(args: list[str]) -> dict[str, str]:
    """인자 중 실제 파일인 것의 해시. 입력이 바뀌면 기준 출력도 다시 만들어야 한다."""
    hashes = {}
    for arg in args:
        path = PROJECT / arg
        if path.is_file():
            hashes[arg] = sha256(path.read_bytes())
    return hashes


def run(cmd: list[str]) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(cmd, cwd=PROJECT, capture_output=True, timeout=600)


def record() -> int:
    GOLDENS.mkdir(exist_ok=True)
    start = time.perf_counter()
    for case in load_cases():
        proc = run([sys.executable, str(REFERENCE), *case["args"]])
        meta = {
            "args": case["args"],
            "usage_error": case.get("usage_error", False),
            "exit_code": proc.returncode,
            "stdout_sha256": sha256(proc.stdout),
            "stderr_sha256": sha256(proc.stderr),
            "inputs": input_hashes(case["args"]),
        }
        store = not case.get("hash_only") and len(proc.stdout) <= INLINE_LIMIT
        if store:
            (GOLDENS / f"{case['name']}.stdout").write_bytes(proc.stdout)
            (GOLDENS / f"{case['name']}.stderr").write_bytes(proc.stderr)
        meta["stored"] = store
        (GOLDENS / f"{case['name']}.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    manifest = {
        "reference_sha256": sha256(REFERENCE.read_bytes()),
        "python": platform.python_version(),
        "unicode": unicodedata.unidata_version,
        "cases": len(load_cases()),
    }
    (GOLDENS / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"recorded {manifest['cases']} cases in {time.perf_counter() - start:.2f}s "
          f"(Python {manifest['python']}, Unicode {manifest['unicode']})")
    return 0


def stale_reasons() -> list[str]:
    manifest = json.loads((GOLDENS / "manifest.json").read_text(encoding="utf-8"))
    reasons = []
    if manifest["reference_sha256"] != sha256(REFERENCE.read_bytes()):
        reasons.append("기준 구현(python_src/wordfreq.py)이 기록 이후 바뀜")
    for case in load_cases():
        meta = json.loads((GOLDENS / f"{case['name']}.json").read_text(encoding="utf-8"))
        if meta["inputs"] != input_hashes(case["args"]):
            reasons.append(f"{case['name']}: 입력 파일이 기록 이후 바뀜")
    return reasons


def check(rust: Path) -> int:
    reasons = stale_reasons()
    if reasons:
        print("기준 출력이 낡았습니다. record 로 다시 기록하고 바뀐 출력을 검토하세요:", file=sys.stderr)
        for reason in reasons:
            print(f"  - {reason}", file=sys.stderr)
        return 3
    start = time.perf_counter()
    failed = 0
    cases = load_cases()
    for case in cases:
        meta = json.loads((GOLDENS / f"{case['name']}.json").read_text(encoding="utf-8"))
        proc = run([str(rust.resolve()), *case["args"]])
        problems = []
        if proc.returncode != meta["exit_code"]:
            problems.append(f"exit code: golden={meta['exit_code']} rust={proc.returncode}")
        if meta["usage_error"]:
            if not proc.stderr:
                problems.append("stderr: rust printed nothing")
        else:
            for stream, data in (("stdout", proc.stdout), ("stderr", proc.stderr)):
                if sha256(data) == meta[f"{stream}_sha256"]:
                    continue
                if meta["stored"]:
                    expected = (GOLDENS / f"{case['name']}.{stream}").read_bytes()
                    problems.append(f"{stream}: golden={expected[:120]!r} rust={data[:120]!r}")
                else:
                    problems.append(f"{stream}: SHA-256 다름 (출력 {len(data):,}바이트, 내용은 저장하지 않아 비교 불가)")
        failed += bool(problems)
        print(f"{'OK  ' if not problems else 'FAIL'} {case['name']}")
        for problem in problems:
            print(f"     {problem}")
    print(f"\n{len(cases) - failed}/{len(cases)} cases match ({time.perf_counter() - start:.2f}s)")
    return 1 if failed else 0


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("record")
    chk = sub.add_parser("check")
    chk.add_argument("--rust", type=Path, required=True)
    args = parser.parse_args()
    return record() if args.command == "record" else check(args.rust)


if __name__ == "__main__":
    sys.exit(main())
