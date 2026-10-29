"""h11 0.16 이 chunked 요청 본문과 특수 헤더를 어떻게 다루는지 실측.

사용법: uv run python verify/probe_h11.py
"""

import h11

GOOD = b'{"name":"a","price":1,"quantity":1}'
CASES = {
    "chunked": b"POST /items HTTP/1.1\r\nHost: x\r\nTransfer-Encoding: chunked\r\n\r\n24\r\n" + GOOD + b"\r\n0\r\n\r\n",
    "chunked-ext-trailer": b"POST /items HTTP/1.1\r\nHost: x\r\nTransfer-Encoding: chunked\r\n\r\n24;a=1\r\n" + GOOD
    + b"\r\n0\r\nX-T: 1\r\n\r\n",
    "cl-te": b"POST /items HTTP/1.1\r\nHost: x\r\nContent-Length: 5\r\nTransfer-Encoding: chunked\r\n\r\n0\r\n\r\n",
    "obs-fold": b"GET / HTTP/1.1\r\nHost: x\r\nX-A: a\r\n b\r\n\r\n",
    "obs-fold-first": b"GET / HTTP/1.1\r\n b\r\nHost: x\r\n\r\n",
}
for name, data in CASES.items():
    conn = h11.Connection(h11.SERVER)
    conn.receive_data(data)
    events = []
    try:
        while True:
            event = conn.next_event()
            events.append(event)
            if event in (h11.NEED_DATA, h11.PAUSED) or isinstance(event, h11.EndOfMessage):
                break
    except h11.RemoteProtocolError as err:
        events.append(f"ERROR {err}")
    print(name, [str(e)[:120] for e in events])
