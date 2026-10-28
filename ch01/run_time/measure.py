"""wordfreq 의 Python 기준 구현과 Rust 구현의 실행 시간을 잰다 (01-2).

입력 두 가지로 잰다.
- small: tests/fixtures/basic.txt (58바이트) — 실행 시간 대부분이 프로그램 시작 비용
- large: 고정 시드로 만든 약 20MB 텍스트 — 실제 처리 비용

사용법 (ch04/wordfreq 에서, Rust 릴리스 빌드 후):
    uv run python ../../ch01/run_time/measure.py
"""

import platform
import random
import statistics
import subprocess
import sys
import time
from pathlib import Path

WORDFREQ = Path.cwd()
DATA = Path(__file__).resolve().parent / "data"
EXE = "wordfreq.exe" if sys.platform == "win32" else "wordfreq"
WARMUP = 3
RUNS = 20


def make_large(path: Path, target_bytes: int = 20_000_000) -> None:
    rng = random.Random(42)
    vocab = [f"w{i}" for i in range(5000)] + ["러스트", "파이썬", "에이전트", "Rust,", "Python."]
    weights = [1 / (rank + 1) for rank in range(len(vocab))]  # 자주 나오는 단어와 드문 단어가 섞이도록
    lines: list[str] = []
    size = 0
    while size < target_bytes:
        line = " ".join(rng.choices(vocab, weights, k=12))
        lines.append(line)
        size += len(line.encode("utf-8")) + 1
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def measure(cmd: list[str]) -> list[float]:
    times = []
    for i in range(WARMUP + RUNS):
        start = time.perf_counter()
        subprocess.run(cmd, cwd=WORDFREQ, capture_output=True, check=True)
        if i >= WARMUP:
            times.append(time.perf_counter() - start)
    return times


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    DATA.mkdir(exist_ok=True)
    large = DATA / "large.txt"
    if not large.exists():
        make_large(large)
    inputs = {"small": WORDFREQ / "tests" / "fixtures" / "basic.txt", "large": large}
    programs = {
        "python": [sys.executable, "python_src/wordfreq.py"],
        "rust": [str(WORDFREQ / "rust_app" / "target" / "release" / EXE)],
    }
    print(f"{platform.platform()} / {platform.processor()} / Python {platform.python_version()}")
    print(f"warmup {WARMUP}, runs {RUNS}, large = {large.stat().st_size:,} bytes")
    for input_name, path in inputs.items():
        for prog_name, cmd in programs.items():
            times = measure([*cmd, str(path)])
            print(
                f"{input_name:<6} {prog_name:<7} median {statistics.median(times) * 1000:8.1f} ms"
                f"  min {min(times) * 1000:8.1f} ms  max {max(times) * 1000:8.1f} ms"
            )
    return 0


if __name__ == "__main__":
    sys.exit(main())
