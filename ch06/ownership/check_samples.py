"""broken/ 의 각 예제가 파일 이름의 오류 코드로 컴파일에 실패하는지 확인하고,
진단을 세 가지 형식(human·short·json)으로 diagnostics/ 에 저장한다 (06-1, 06-2).

사용법 (ch06/ownership 에서): python3 check_samples.py
"""

import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
BROKEN = HERE / "broken"
OUT = HERE / "diagnostics"
FORMATS = {"human": ".txt", "short": ".short.txt", "json": ".json"}


def compile_sample(src: Path, fmt: str, out_dir: str) -> subprocess.CompletedProcess[str]:
    cmd = [
        "rustc", "--edition", "2024", "--crate-type", "lib", "--emit", "metadata",
        "--out-dir", out_dir, "--color", "never", "--error-format", fmt,
        str(src.relative_to(HERE)),
    ]
    return subprocess.run(cmd, cwd=HERE, capture_output=True, text=True)


def summarize_json(stderr: str) -> tuple[list[str], int, list[str]]:
    """json 진단에서 오류 코드 목록, 메시지 수, 수정 제안의 적용 가능성 목록을 뽑는다."""
    codes: list[str] = []
    applicability: list[str] = []
    messages = 0
    for line in stderr.splitlines():
        if not line.startswith("{"):
            continue
        diag = json.loads(line)
        if diag.get("level") != "error":
            continue
        messages += 1
        if diag.get("code"):
            codes.append(diag["code"]["code"])
        for child in diag.get("children", []):
            for span in child.get("spans", []):
                if span.get("suggested_replacement") is not None:
                    applicability.append(span.get("suggestion_applicability") or "None")
    return codes, messages, applicability


def main() -> int:
    OUT.mkdir(exist_ok=True)
    failures = 0
    print(f"{'예제':<34} {'기대':<6} {'실제':<14} {'human':>6} {'short':>6} {'json':>6}  제안(적용 가능성)")
    with tempfile.TemporaryDirectory() as tmp:
        for src in sorted(BROKEN.glob("*.rs")):
            expected = re.match(r"e(\d{4})_", src.name).group(1)
            sizes = {}
            json_stderr = ""
            for fmt, suffix in FORMATS.items():
                proc = compile_sample(src, fmt, tmp)
                (OUT / (src.stem + suffix)).write_text(proc.stderr, encoding="utf-8")
                sizes[fmt] = len(proc.stderr.encode("utf-8"))
                if fmt == "json":
                    json_stderr = proc.stderr
                    returncode = proc.returncode
            codes, _, applicability = summarize_json(json_stderr)
            ok = returncode != 0 and f"E{expected}" in codes
            failures += not ok
            print(
                f"{src.name:<34} E{expected:<5} {','.join(codes) or '-':<14} "
                f"{sizes['human']:>6} {sizes['short']:>6} {sizes['json']:>6}  "
                f"{','.join(applicability) or '없음'}{'' if ok else '  <-- 기대와 다름'}"
            )
    print(f"\n{'모두 기대한 오류' if failures == 0 else f'{failures}개가 기대와 다름'}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
