"""게이트가 에이전트의 코드를 실행하는 환경을 확인한다 (12-4).

    uv run python examples/gate_probe.py

게이트와 같은 방법(gate.sandbox_prefix + gate.clean_env)으로 작은 Python 코드를 실행해,
비밀 환경 변수·인증 정보 폴더·네트워크·작업 폴더 밖 쓰기가 막혔는지 본다. 비교를 위해 격리 없이도 한 번 실행한다.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from rustify_lib.gate import clean_env, sandbox_prefix  # noqa: E402

PROBE = r"""
import os, socket
from pathlib import Path
home = Path.home()
def attempt(label, fn):
    try:
        result = fn()
        print(f"{label}: 가능 {result if result is not None else ''}".rstrip())
    except Exception as err:
        print(f"{label}: 막힘 ({type(err).__name__})")
attempt("비밀 환경 변수", lambda: sorted(k for k in os.environ if "PROBE_SECRET" in k) or (_ for _ in ()).throw(KeyError("없음")))
attempt("~/.claude 읽기", lambda: len(list((home / ".claude").iterdir())) or (_ for _ in ()).throw(FileNotFoundError("비어 있음")))
attempt("crates.io 접속", lambda: socket.create_connection(("crates.io", 443), 3).close())
attempt("작업 폴더에 쓰기", lambda: Path("probe.txt").write_text("x"))
attempt("홈 폴더에 쓰기", lambda: (home / "rustify_probe.txt").write_text("x"))
"""


def main() -> int:
    os.environ["PROBE_SECRET_TOKEN"] = "not-a-real-secret"  # 게이트가 이름에 TOKEN 이 든 변수를 지우는지 본다
    with tempfile.TemporaryDirectory(dir=Path.home() / "work") as tmp:
        workspace = Path(tmp)
        for label, prefix, env in [("격리 없음", [], dict(os.environ)),
                                   ("게이트(격리)", sandbox_prefix(workspace), clean_env(workspace))]:
            print(f"== {label}", flush=True)
            subprocess.run(prefix + [sys.executable, "-c", PROBE], cwd=workspace, env=env)
    (Path.home() / "rustify_probe.txt").unlink(missing_ok=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
