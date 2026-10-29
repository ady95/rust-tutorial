"""실수→정수 경계(int_parsing_size)와 JSON 오류 위치를 실측한다.

사용법: uv run python verify/probe_lax5.py
"""

import json
import math

from probe_lax import INT, QTY, run

TWO63 = 2.0**63
for v in [TWO63, -TWO63, math.nextafter(TWO63, 0), math.nextafter(-TWO63, 0), math.nextafter(TWO63, math.inf),
          math.nextafter(-TWO63, -math.inf), 1e300, -1e300, 4e18, -0.0]:
    print(f"int {v!r}: {run(INT, v)[:50]} qty={run(QTY, v)[:40]}")

DOCS = ['{"name":"é", "price": 1,', '{"a" 1}', '{"a":1,}', '[1,]', '{', '"\x01"', '"\\q"', '"\\u12"', '"abc', '-', '01',
        '1.', 'tru', ' ', '﻿{}', '"\\u12345"', '"\\ud800\\u12"', '"\\ud800\\uzzzz"', '"\\ud800\\u"', '[1 2]',
        '{"a":}', '{"a":1 "b"}', '[', '{"a"', '"\\', '"\\u', '"\\u1234', 'nul', 'NaN1', '-Infinit', '1e', '1e+', '1.e5',
        '-a', '[-]', '{"a":1,"a"', '  {"a":1}  x', '"a\\u00e9\x7f"', '[]]', '{}{}', '{"\\ud800":1']
for doc in DOCS:
    try:
        print(f"json {doc!r}: OK {json.loads(doc)!r:.40}")
    except json.JSONDecodeError as err:
        print(f"json {doc!r}: pos={err.pos} {err.msg}")
