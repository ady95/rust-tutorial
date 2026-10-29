"""무작위 로그 파일로 기준 구현과 Rust 구현을 비교한다 (Hypothesis, 07-2 방식).

레코드마다 필드를 '올바른 값'과 '경계·잘못된 값' 중에서 고르고, CSV 또는 JSON Lines 로 써서 두 구현에 넣는다.
기대 출력은 기준 구현의 run() 을 같은 프로세스에서 불러 만들고(main 과 같은 결과), Rust 는 실행 파일로 돌린다.
seed 를 주지 않으면 실행할 때마다 다른 입력을 만든다.

사용법 (프로젝트 루트에서): uv run python automation/fuzz.py [--rust BIN] [--examples 1500] [--seed N]
종료 코드: 0 = 차이 없음, 1 = 차이 발견, 2 = Rust 실행 파일 없음
"""

from __future__ import annotations

import argparse
import csv
import importlib.util
import io
import json
import subprocess
import sys
import tempfile
from pathlib import Path

from hypothesis import given, seed, settings
from hypothesis import strategies as st

ROOT = Path(__file__).resolve().parent.parent
REFERENCE = ROOT / "python_src" / "logstat.py"

_spec = importlib.util.spec_from_file_location("logstat_ref", REFERENCE)
ref = importlib.util.module_from_spec(_spec)
sys.modules["logstat_ref"] = ref  # dataclass 가 모듈을 찾을 수 있도록 실행 전에 등록
_spec.loader.exec_module(ref)

FIELDS = ["ts", "method", "path", "status", "bytes", "latency_ms"]

digits = st.integers(0, 9).map(str)
offset = st.one_of(st.just("Z"), st.builds(lambda s, h, m: f"{s}{h:02d}:{m:02d}", st.sampled_from("+-"),
                                           st.integers(0, 25), st.sampled_from([0, 30, 59, 60])))
valid_ts = st.builds(
    lambda y, mo, d, h, mi, s, frac, off: f"{y:04d}-{mo:02d}-{d:02d}T{h:02d}:{mi:02d}:{s:02d}{frac}{off}",
    st.sampled_from([1, 999, 2026, 9999]) | st.integers(1, 9999), st.integers(1, 12), st.integers(1, 31),
    st.integers(0, 24), st.integers(0, 59), st.integers(0, 60),
    st.one_of(st.just(""), st.text(digits, min_size=1, max_size=7).map(lambda f: "." + f)), offset)
# 올바른 값을 더 자주 뽑아(가지를 반복) 집계 로직도 충분히 시험되게 한다
ts = st.one_of(valid_ts, valid_ts, valid_ts, valid_ts.map(lambda t: t.replace("2", "٢", 1)), st.text(max_size=12))
method = st.sampled_from(["GET"] * 6 + ["POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS", "get", "TRACE", ""])
path = st.one_of(st.sampled_from(["/a", "/b", "/a/b"]), st.sampled_from(["/a", "/b", "/a/b"]),
                 st.text(max_size=12).map(lambda p: "/" + p), st.text(max_size=6),
                 st.sampled_from(["/", "/a?x=1", "/a?", "/a,b", '/"q"', "/a\nb", "/ ", "/é"]))
number_text = st.one_of(st.integers(0, 10**13).map(str), st.text("0123456789.e-+ ", max_size=8),
                        st.sampled_from(["0", "00", "1e3", ".5", "1.", "0.00001", "1" + "0" * 30, "２"]))
json_number = st.one_of(st.integers(-5, 10**13), st.floats(allow_nan=True, allow_infinity=True), st.booleans(),
                        st.sampled_from([200, 404, 500, 599, 600, 99, 10**12, 10**12 + 1, 1e9, 1e9 + 1]),
                        number_text)
row = st.fixed_dictionaries({
    "ts": ts, "method": method, "path": path,
    "status": st.one_of(*[st.sampled_from([200, 301, 404, 500, 503])] * 3, number_text, json_number),
    "bytes": st.one_of(*[st.integers(0, 100000)] * 3, number_text, json_number),
    "latency_ms": st.one_of(*[st.floats(0, 5000, allow_nan=False).map(lambda x: round(x, 3))] * 3, number_text,
                            json_number),
})
rows = st.lists(row, max_size=25)


def to_csv(records: list[dict], drop: str | None) -> str:
    buf = io.StringIO(newline="")
    header = [f for f in FIELDS if f != drop]
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(header)
    for r in records:
        writer.writerow([r[f] if isinstance(r[f], str) else json.dumps(r[f]) for f in header])
    return buf.getvalue()


def to_jsonl(records: list[dict], drop: str | None) -> str:
    return "".join(json.dumps({k: v for k, v in r.items() if k != drop}, ensure_ascii=False) + "\n" for r in records)


def actual(binary: Path, path: Path, top: int, as_json: bool, strict: bool) -> tuple[int, str, str]:
    cmd = [str(binary), str(path), "--top", str(top)] + (["--json"] if as_json else []) + (["--strict"] if strict else [])
    proc = subprocess.run(cmd, capture_output=True, timeout=60)
    return proc.returncode, proc.stdout.decode("utf-8", "replace"), proc.stderr.decode("utf-8", "replace")


def main() -> int:
    parser = argparse.ArgumentParser(description="Random differential test against the reference.")
    parser.add_argument("--rust", type=Path, default=ROOT / "rust_app" / "target" / "release" / "logstat")
    parser.add_argument("--examples", type=int, default=1500)
    parser.add_argument("--seed", type=int)
    args = parser.parse_args()
    if not args.rust.exists():
        print(f"Rust binary not found: {args.rust}", file=sys.stderr)
        return 2
    binary = args.rust.resolve()
    tmp = Path(tempfile.mkdtemp())
    failure: dict[str, object] = {}

    @settings(max_examples=args.examples, deadline=None, database=None)
    @given(records=rows, fmt=st.sampled_from(["csv", "jsonl"]), drop=st.one_of(st.none(), st.sampled_from(FIELDS)),
           top=st.integers(1, 5), as_json=st.booleans(), strict=st.booleans())
    def check(records: list[dict], fmt: str, drop: str | None, top: int, as_json: bool, strict: bool) -> None:
        if drop is not None and len(records) > 3:
            drop = None  # 필드를 빼는 경우는 작은 입력에서만
        text = to_csv(records, drop) if fmt == "csv" else to_jsonl(records, drop)
        path = tmp / f"input.{fmt}"
        path.write_bytes(text.encode("utf-8", "surrogatepass"))
        try:
            expected = ref.run(path.read_bytes().decode("utf-8"), fmt, top, as_json, strict)
        except UnicodeDecodeError:
            return  # 서로게이트가 들어간 입력은 두 구현 모두 'not valid UTF-8' 이라 여기서는 건너뛴다
        got = actual(binary, path, top, as_json, strict)
        if expected != got:
            failure.update(text=text, fmt=fmt, args=(top, as_json, strict), python=expected, rust=got)
        assert expected == got

    if args.seed is not None:
        check = seed(args.seed)(check)
    try:
        check()
    except AssertionError:
        # Hypothesis 는 줄인 뒤의 마지막 실패 입력으로 한 번 더 실행하므로 failure 에는 최소 입력이 남는다
        print("FAIL random input differs")
        print(f"     format={failure['fmt']} top/json/strict={failure['args']}")
        print(f"     input={str(failure['text'])[:400]!r}")
        print(f"     python: {str(failure['python'])[:400]!r}")
        print(f"     rust:   {str(failure['rust'])[:400]!r}")
        return 1
    print(f"OK   {args.examples} random inputs match")
    return 0


if __name__ == "__main__":
    sys.exit(main())
