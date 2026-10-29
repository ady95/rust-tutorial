"""기준 구현의 argparse 도움말과 Python 버전을 출력한다(Rust 도움말 문구를 맞추기 위함)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "python_src"))

import logstat  # noqa: E402

print(sys.version)
print(repr(logstat.build_parser().format_help()))
