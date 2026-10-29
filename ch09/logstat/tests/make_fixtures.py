"""tests/fixtures/ 의 입력 파일을 만든다. 파일은 바이트 그대로가 계약이므로 이 스크립트로만 다시 만든다."""

from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent / "fixtures"
HEADER = "ts,method,path,status,bytes,latency_ms"

BASIC = [
    ("2026-10-29T09:00:01Z", "GET", "/", 200, 512, 12.5),
    ("2026-10-29T09:00:02Z", "GET", "/api/users?id=1", 200, 1024, 30.25),
    ("2026-10-29T09:00:02.250Z", "POST", "/api/users", 201, 64, 48.0),
    ("2026-10-29T18:00:03+09:00", "GET", "/api/users?id=2", 500, 0, 250.125),
    ("2026-10-29T09:00:59Z", "GET", "/static/app.js", 304, 0, 1.5),
    ("2026-10-29T09:01:00Z", "GET", "/api/users", 404, 128, 3.0),
    ("2026-10-29T09:01:10Z", "DELETE", "/api/users/7", 204, 0, 15.75),
    ("2026-10-29T09:01:20Z", "GET", "/", 200, 512, 0.00001),
    ("2026-10-29T09:01:30Z", "GET", "/api/orders", 502, 0, 1200.0),
    ("2026-10-29T09:01:31Z", "GET", "/api/orders", 200, 2048, 80.5),
]


def write(name: str, text: str) -> None:
    (HERE / name).write_bytes(text.encode("utf-8"))


def decimal(x: float) -> str:
    """CSV 규칙은 지수 표기를 받지 않으므로 repr 이 1e-05 처럼 나오는 값은 소수로 쓴다."""
    text = repr(x)
    return format(x, "f") if "e" in text else text


def csv_rows(rows: list[tuple]) -> list[str]:
    return [f"{ts},{m},{p},{s},{b},{decimal(lat)}" for ts, m, p, s, b, lat in rows]


def main() -> None:
    HERE.mkdir(exist_ok=True)
    bad_csv = ["2026-10-29T09:02:00Z,get,/x,200,1,1", "2026-10-29T09:02:00Z,GET,/x,600,1,1", "not-a-time,GET,/x,200,1,1",
               "2026-10-29T09:02:00Z,GET,x,200,1,1", "2026-10-29T09:02:00Z,GET,/x,200,1"]
    write("basic.csv", "\n".join([HEADER, *csv_rows(BASIC), *bad_csv]) + "\n")
    lines = [json.dumps(dict(zip(HEADER.split(","), r))) for r in BASIC]
    lines += ['{"ts":"2026-10-29T09:02:00Z","method":"GET","path":"/x","status":true,"bytes":1,"latency_ms":1}',
              '{"ts":"2026-10-29T09:02:00Z","method":"GET","path":"/x","status":200,"bytes":1}', "[1,2,3]", "{oops"]
    write("basic.jsonl", "\n".join(lines) + "\n")
    # 인용, 쉼표·따옴표·줄바꿈이 든 필드, 열 순서 바꾸기, 여분의 열, CRLF, 빈 줄
    quoting = ('latency_ms,extra,ts,path,method,bytes,status\r\n'
               '1.25,"a,b",2026-10-29T10:00:00Z,"/q/""quoted""",GET,10,200\r\n'
               '\r\n'
               '2.5,"line1\nline2",2026-10-29T10:00:01Z,"/q/a,b?x=1",POST,20,201\r\n'
               '3.75,,2026-10-29T10:00:02Z,/q/한글,GET,30,503\r\n')
    write("quoting.csv", quoting)
    edge = ['{"ts":"2026-10-29T10:00:00Z","method":"GET","path":"/e","status":500,"status":200,"bytes":1,"latency_ms":2}',
            '{"ts":"2026-10-29T10:00:00Z","method":"GET","path":"/e","status":200,"bytes":1,"latency_ms":NaN}',
            '{"ts":"2026-10-29T10:00:00Z","method":"GET","path":"/e","status":200.0,"bytes":1,"latency_ms":2}',
            '{"ts":"2026-10-29T10:00:00Z","method":"GET","path":"/e","status":200,"bytes":1000000000001,"latency_ms":2}',
            '{"ts":"2026-10-29T10:00:00Z","method":"GET","path":"/e","status":200,"bytes":1,"latency_ms":1e3,"x":[[[]]]}',
            '   ',
            '{"ts":"2026-10-29T10:00:00.1Z","method":"HEAD","path":"/ line","status":200,"bytes":0,"latency_ms":0}',
            '{"ts":"2026-10-29T23:59:60Z","method":"GET","path":"/e","status":200,"bytes":1,"latency_ms":2}',
            '{"ts":"0001-01-01T00:00:00+00:01","method":"GET","path":"/e","status":200,"bytes":1,"latency_ms":2}',
            '{"ts":"2026-10-29T10:00:00٣Z","method":"GET","path":"/e","status":200,"bytes":1,"latency_ms":2}']
    write("edge.jsonl", "\n".join(edge) + "\r\n")
    tz = [json.dumps({"ts": ts, "method": "GET", "path": "/t", "status": 200, "bytes": 1, "latency_ms": 1}) for ts in
          ["2026-10-29T10:00:30+00:00", "2026-10-29T19:00:10+09:00", "2026-10-29T10:01:00Z", "2026-10-29T10:01:59.999999Z",
           "2026-10-28T23:01:00-11:00", "2026-10-29T10:00:00.000001Z"]]
    write("tz.jsonl", "\n".join(tz) + "\n")
    write("empty.csv", "")
    write("header_only.csv", HEADER + "\n")
    write("missing_column.csv", "ts,method,path,status,bytes\n2026-10-29T10:00:00Z,GET,/,200,1\n")
    write("bom.csv", "﻿" + HEADER + "\n" + csv_rows(BASIC[:1])[0] + "\n")
    (HERE / "bad_utf8.csv").write_bytes((HEADER + "\n2026-10-29T10:00:00Z,GET,/\xff,200,1,1\n").encode("latin-1"))
    write("big_field.csv", HEADER + "\n" + csv_rows(BASIC[:1])[0] + "\n2026-10-29T10:00:00Z,GET,/" + "x" * 131072 + ",200,1,1\n")
    write("log.txt", "\n".join(lines[:2]) + "\n")


if __name__ == "__main__":
    main()
