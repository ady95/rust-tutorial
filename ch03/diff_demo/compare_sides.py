"""python_side.py 와 rust_side 의 출력을 항목별로 나란히 놓는다 (03-2).

사용법 (ch03/diff_demo 에서):
    cargo build --release --manifest-path rust_side/Cargo.toml
    uv run --no-project python compare_sides.py
"""

import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXE = "rust_side.exe" if sys.platform == "win32" else "rust_side"


def raw(cmd: list[str]) -> bytes:
    return subprocess.run(cmd, cwd=HERE, capture_output=True, check=True).stdout


def lines(cmd: list[str]) -> dict[str, str]:
    out = raw(cmd).decode("utf-8")
    return dict(line.split("\t", 1) for line in out.splitlines())


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    rust_cmd = [str(HERE / "rust_side" / "target" / "release" / EXE)]
    py = lines([sys.executable, "python_side.py"])
    rs = lines(rust_cmd)
    same = 0
    for name, py_value in py.items():
        rs_value = rs.get(name, "(없음)")
        mark = "same" if py_value == rs_value else "DIFF"
        same += mark == "same"
        print(f"{mark}  {name:<22} python={py_value!r:<28} rust={rs_value!r}")
    print(f"\n{same}/{len(py)} same")
    # 줄바꿈: python_side.py 는 newline="\n" 으로 고정했다. 고정하지 않은 print 는 어떨까
    print("python print('a') bytes:", raw([sys.executable, "-c", "print('a')"]))
    print("rust stdout has CR:", b"\r" in raw(rust_cmd))
    return 0


if __name__ == "__main__":
    sys.exit(main())
