"""Rust 함수와 기준(Python·pydantic·Starlette) 함수를 넓은 입력 공간에서 비교한다.

사용법(프로젝트 루트에서):
    uv run python verify/exhaustive.py gen
    cargo test --manifest-path rust_app/Cargo.toml -- --ignored dump_for_verify
    uv run python verify/exhaustive.py check

입력 파일 verify/data/<kind>.in 을 만들고 기대값을 <kind>.expected 에 쓴다.
코드 포인트 전수(intsweep, floatsweep)는 모든 코드 포인트(서로게이트 제외)를 템플릿 6개에 넣어 본다
(경로·쿼리 문자열은 unquote(errors="replace") 를 거치므로 서로게이트가 올 수 없고,
JSON 문자열의 서로게이트는 string_unicode 로 먼저 걸러진다).
"""

from __future__ import annotations

import email.message
import itertools
import json
import math
import random
import struct
import sys
from pathlib import Path
from urllib.parse import unquote

from pydantic import TypeAdapter, ValidationError
from pydantic_core import to_json
from starlette._utils import parse_host_header

DATA = Path(__file__).resolve().parent / "data"
INT, FLOAT = TypeAdapter(int), TypeAdapter(float)
INT_TEMPLATES = ["X", "X5", "5X", "5X0", "+X1", " X5"]
FLOAT_TEMPLATES = ["X", "X1", "1X", "1X5", "1eX5", " X1"]
CODE_POINTS = [c for c in range(0x110000) if not 0xD800 <= c <= 0xDFFF]


def int_result(s: str) -> str:
    try:
        return f"ok {INT.validate_python(s)}"
    except ValidationError as err:
        return f"err {err.errors()[0]['type']}"


def float_result(s: str) -> str:
    try:
        v = FLOAT.validate_python(s)
    except ValidationError as err:
        return f"err {err.errors()[0]['type']}"
    return "ok nan" if math.isnan(v) else "ok " + struct.pack(">d", v).hex()


def cps(s: str) -> str:
    return " ".join(f"{ord(c):x}" for c in s)


def json_decode(b: bytes) -> str:
    try:
        return "ok " + cps(b.decode(json.detect_encoding(b), "surrogatepass"))
    except UnicodeDecodeError:
        return "err"


def json_load(b: bytes) -> str:
    try:
        json.loads(b)
        return "ok"
    except json.JSONDecodeError as err:
        return f"pos {err.pos}"
    except (ValueError, RecursionError):  # UnicodeDecodeError, 정수 자릿수 초과 등 → FastAPI 400
        return "other"


def ctype(b: bytes) -> str:
    message = email.message.Message()
    message["content-type"] = b.decode("latin-1")
    sub = message.get_content_subtype()
    return "1" if message.get_content_maintype() == "application" and (sub == "json" or sub.endswith("+json")) else "0"


def host(b: bytes) -> str:
    parsed = parse_host_header(b.decode("latin-1"))
    return parsed.authority if parsed is not None and parsed.is_valid_port else "<none>"


def float_fmt(b: bytes) -> str:
    return to_json(struct.unpack(">d", b)[0]).decode()


def rand_join(rng: random.Random, tokens: list, low: int, high: int) -> str | bytes:
    picked = [rng.choice(tokens) for _ in range(rng.randint(low, high))]
    return (b"" if isinstance(tokens[0], bytes) else "").join(picked)


def inputs(rng: random.Random) -> dict[str, tuple[list[bytes], object]]:
    out: dict[str, tuple[list[bytes], object]] = {}
    # 문자열→정수/실수: 무작위 조합(코드 포인트 전수는 sweep 이 맡는다)
    toks = ["0", "1", "9", "_", "-", "+", ".", " ", "e", "E", "x", "inf", "nan", " ", "　", "\x1c", "٥",
            "infinity", "N", "a", "\t", "\n", "00", "5"]
    strs = sorted({rand_join(rng, toks, 0, 8) for _ in range(300_000)})
    strs += [p + d * n + q for d in "019" for n in (4298, 4299, 4300, 4301, 4302) for p in ("", "-", "+", " ", "0")
             for q in ("", ".0", "_", "x", " ")]
    out["intstr"] = ([s.encode() for s in strs], lambda b: int_result(b.decode()))
    out["floatstr"] = ([s.encode() for s in strs], lambda b: float_result(b.decode()))
    # 퍼센트 디코딩: 1~2바이트 전부, 3바이트는 대표 바이트 집합으로 전부, 그리고 무작위 % 조합
    rep = [0x41, 0x80, 0x8F, 0x90, 0x9F, 0xA0, 0xBF, *range(0xC0, 0x100)]
    seqs = [bytes([a]) for a in range(256)] + [bytes([a, b]) for a in range(256) for b in range(256)]
    seqs += [bytes(t) for t in itertools.product(rep, repeat=3)]
    seqs += [bytes(t) for t in itertools.product([0xF0, 0xF4, 0xF5, 0xED, 0xE0], [0x80, 0x8F, 0x90, 0xBF], rep, rep)]
    quoted = ["".join(f"%{x:02X}" for x in s) for s in seqs]
    ptoks = ["%", "A", "f", "g", "0", "9", "%2", "%E9", "%C3", "%A9", "%e9", "+", "x", "%%", "%F0%9F", "%98%80"]
    quoted += sorted({rand_join(rng, ptoks, 0, 8) for _ in range(100_000)})
    out["unquote"] = ([q.encode() for q in quoted], lambda b: cps(unquote(b.decode())))
    # json.loads(bytes) 의 인코딩 감지 + surrogatepass
    jrep = [0x00, 0x22, 0x41, 0x7B, 0x80, 0xBF, 0xA0, 0xC2, 0xD8, 0xDC, 0xDF, 0xE0, 0xED, 0xEF, 0xBB, 0xF0, 0xF4,
            0xFE, 0xFF]
    jseqs = [bytes(t) for n in range(1, 5) for t in itertools.product(jrep, repeat=n)]
    jseqs += [bytes(rng.choice(jrep) for _ in range(rng.randint(5, 12))) for _ in range(200_000)]
    out["jsondecode"] = (jseqs, json_decode)
    # json.loads 전체(오류 위치): JSON 조각 무작위 조합
    jtoks = ['{', '}', '[', ']', ',', ':', '"', '"a"', '\\', '\\u', '\\ud800', '\\udc00', 'd800', '12', '1', '0', '-',
             '.', 'e', '+', ' ', '\n', '\t', 'null', 'true', 'nul', 'NaN', 'Infinity', '-Infinity', 'é', '😀', '\x01',
             'x', 'u', '"\\u00e9"', '1e5', '-0', '01']
    docs = sorted({rand_join(rng, jtoks, 1, 10) for _ in range(300_000)})
    out["jsonload"] = ([d.encode() for d in docs] + [d.encode("utf-16") for d in docs[:5000]], json_load)
    # Content-Type: latin-1 바이트 전부를 여러 위치에(h11 이 막는 NUL/CR/LF/VT/FF 와, 끝에서 떼는 SP/HTAB 제외)
    allowed = [b for b in range(1, 256) if b not in (0x0A, 0x0D, 0x0B, 0x0C)]
    ct = []
    for x in allowed:
        c = bytes([x])
        for t in (c + b"application/json", b"application/json" + c, b"application" + c + b"/json", b"app" + c + b"lication/json",
                  c + b"application/json;x", b"application/json" + c + b";x", b"application/" + c + b"+json",
                  b"APPLICATION/JSON" + c, b"application/vnd" + c + b"+json"):
            ct.append(t)
    ctoks = [b"application", b"json", b"/", b";", b"+", b" ", b"\x1c", b"\xa0", b"\x85", b"JSON", b"x", b"text", b"\xc0"]
    ct += sorted({rand_join(rng, ctoks, 1, 6) for _ in range(50_000)})
    out["ctype"] = (ct, ctype)
    # Host 헤더: 모든 latin-1 바이트 + IPv6 표기 + 무작위
    hosts = [bytes([x]) for x in allowed] + [b"h" + bytes([x]) + b"t:80" for x in allowed]
    v6 = ["::1", "::", "1::", "::ffff:1.2.3.4", "1:2:3:4:5:6:7:8", "1:2:3:4:5:6:7::", "::2:3:4:5:6:7:8", "1::2::3",
          "12345::1", "::ffff:01.2.3.4", "::ffff:1.2.3", "::ffff:256.1.1.1", "fe80::1", "FE80::A", "1:2:3:4:5:6:1.2.3.4",
          "1:2:3:4:5:6:7:1.2.3.4", "::1.2.3.4", "1:2:3:4:5:6:7", ":1::", "1:::2", "0000:0000::0001", "00000::1", "::0:0"]
    hosts += [f"[{a}]{p}".encode() for a in v6 for p in ("", ":1", ":65535", ":65536", ":000080", ":")]
    htoks = ["a", "Z", "0", "9", ":", "[", "]", ".", "-", "%", "v", "V", "::", "1", "ff", "ffff", "1.2.3.4", "@", " ",
             "\xe9", "_", "~", "*", "65535", "65536", "00000"]
    hosts += sorted({rand_join(rng, htoks, 1, 8).encode("latin-1") for _ in range(200_000)})
    out["host"] = (hosts, host)
    # 실수 표기: 무작위 비트 패턴 + 10의 거듭제곱·2의 거듭제곱 주변 + 비정규수 경계
    vals = [struct.unpack(">d", rng.getrandbits(64).to_bytes(8, "big"))[0] for _ in range(1_000_000)]
    vals += [rng.uniform(0, 1e6) for _ in range(200_000)] + [round(rng.uniform(0, 1e6), rng.randint(0, 9)) for _ in range(200_000)]
    for e in range(-324, 309):
        for base in (1.0, 9.999999999999999, 5.0, 1.5):
            v = base * 10.0**e if abs(e) < 300 else float(f"{base}e{e}")
            vals += [v, math.nextafter(v, 0), math.nextafter(v, math.inf)]
    vals += [2.0**k for k in range(-1074, 1024)] + [5e-324 * k for k in range(1, 1000)] + [-0.0, 0.0]
    vals = [v for v in vals if math.isfinite(v)]
    out["floatfmt"] = ([struct.pack(">d", v) for v in vals], float_fmt)
    return out


def gen() -> None:
    DATA.mkdir(exist_ok=True)
    for kind, (items, fn) in inputs(random.Random(20261029)).items():
        (DATA / f"{kind}.in").write_text("".join(b.hex() + "\n" for b in items))
        (DATA / f"{kind}.expected").write_text("".join(fn(b) + "\n" for b in items))
        print(f"{kind}: {len(items)} inputs")
    for kind, templates, default, fn in (("intsweep", INT_TEMPLATES, "err int_parsing", int_result),
                                         ("floatsweep", FLOAT_TEMPLATES, "err float_parsing", float_result)):
        lines = []
        for ti, t in enumerate(templates):
            for c in CODE_POINTS:
                r = fn(t.replace("X", chr(c)))
                if r != default:
                    lines.append(f"{ti} {c:x} {r}\n")
        (DATA / f"{kind}.expected").write_text("".join(lines))
        print(f"{kind}: {len(templates) * len(CODE_POINTS)} inputs, {len(lines)} non-default")


def check() -> int:
    bad = 0
    for expected in sorted(DATA.glob("*.expected")):
        kind = expected.stem
        rust = DATA / f"{kind}.rust"
        want = expected.read_text().splitlines()
        got = rust.read_text().splitlines() if rust.exists() else []
        inputs_ = (DATA / f"{kind}.in").read_text().splitlines() if (DATA / f"{kind}.in").exists() else None
        diffs = [i for i in range(max(len(want), len(got)))
                 if (want[i] if i < len(want) else None) != (got[i] if i < len(got) else None)]
        bad += bool(diffs)
        print(f"{'OK  ' if not diffs else 'FAIL'} {kind}: {len(want)} lines, {len(diffs)} differ")
        if kind == "floatfmt" and diffs:
            # 계약 4절은 "지수에 + 없음", pydantic-core 는 양수 지수에 '+' 를 붙인다. 그 차이만인지 본다
            other = [i for i in diffs if want[i].replace("e+", "e") != got[i]]
            print(f"     ('e+' 를 'e' 로 바꾸면 {len(other)} differ)")
            for i in other[:10]:
                print(f"       python={want[i]} rust={got[i]}")
        for i in diffs[:8]:
            shown = bytes.fromhex(inputs_[i]) if inputs_ and i < len(inputs_) else ""
            print(f"     {shown!r:.80} python={(want[i] if i < len(want) else None)!r:.80} "
                  f"rust={(got[i] if i < len(got) else None)!r:.80}")
    return 1 if bad else 0


if __name__ == "__main__":
    if sys.argv[1:] == ["gen"]:
        gen()
    elif sys.argv[1:] == ["check"]:
        sys.exit(check())
    else:
        sys.exit("usage: exhaustive.py gen|check")
