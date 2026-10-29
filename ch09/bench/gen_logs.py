"""벤치마크용 접근 로그를 만든다 (09-1). 같은 seed 면 같은 파일이 나온다.

- 경로 2,000개, 순위가 낮을수록 자주 나옴(Zipf 비슷한 분포), 20%는 쿼리 문자열이 붙음
- 하루(2026-10-29 UTC) 동안 시간 순서로 퍼짐, 시각의 20%는 +09:00 오프셋, 밀리초 3자리
- latency_ms 는 로그정규 분포, 소수 셋째 자리까지
- 레코드의 0.1%는 잘못된 값(계약 3절의 각 규칙을 하나씩 어김)

사용법: python3 gen_logs.py --records 1000000 --out data/logs_1m [--seed 2026]
         → data/logs_1m.csv 와 data/logs_1m.jsonl (같은 레코드)
"""

from __future__ import annotations

import argparse
import bisect
import json
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

METHODS = ["GET"] * 80 + ["POST"] * 12 + ["PUT"] * 3 + ["DELETE"] * 3 + ["PATCH", "HEAD"]
STATUSES = [200] * 85 + [201] * 3 + [204] * 2 + [301, 304, 304] + [400, 401, 404, 404, 404] + [500, 502]
KST = timezone(timedelta(hours=9))
DAY = datetime(2026, 10, 29, tzinfo=timezone.utc)


def make_paths(rng: random.Random, n: int) -> list[str]:
    parts = ["api", "v1", "v2", "users", "orders", "items", "search", "static", "img", "auth", "cart", "admin"]
    paths = set()
    while len(paths) < n:
        depth = rng.randint(1, 4)
        segs = [rng.choice(parts) if rng.random() < 0.7 else str(rng.randint(1, 9999)) for _ in range(depth)]
        paths.add("/" + "/".join(segs))
    return sorted(paths)


def bad(rec: dict[str, object], rng: random.Random) -> dict[str, object]:
    kind = rng.randrange(6)
    rec = dict(rec)
    if kind == 0:
        rec["method"] = "get"
    elif kind == 1:
        rec["status"] = 600
    elif kind == 2:
        rec["ts"] = "2026-10-29 12:00:00"
    elif kind == 3:
        rec["path"] = "no-slash"
    elif kind == 4:
        rec["latency_ms"] = -1
    else:
        rec["bytes"] = 10**13
    return rec


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--records", type=int, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=2026)
    args = parser.parse_args()
    rng = random.Random(args.seed)
    paths = make_paths(rng, 2000)
    weights = [1 / (i + 1) ** 1.1 for i in range(len(paths))]
    cum = []
    total = 0.0
    for w in weights:
        total += w
        cum.append(total)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    step = 86400 / args.records
    with open(args.out.with_suffix(".csv"), "w", encoding="utf-8", newline="\n") as fc, \
            open(args.out.with_suffix(".jsonl"), "w", encoding="utf-8", newline="\n") as fj:
        fc.write("ts,method,path,status,bytes,latency_ms\n")
        for i in range(args.records):
            moment = DAY + timedelta(seconds=i * step + rng.random() * step)
            moment = moment.replace(microsecond=moment.microsecond // 1000 * 1000)
            if rng.random() < 0.2:
                ts = moment.astimezone(KST).isoformat(timespec="milliseconds")
            else:
                ts = moment.isoformat(timespec="milliseconds").replace("+00:00", "Z")
            idx = min(bisect.bisect_left(cum, rng.random() * total), len(paths) - 1)
            path = paths[idx] + (f"?page={rng.randint(1, 50)}" if rng.random() < 0.2 else "")
            status = rng.choice(STATUSES)
            size = 0 if status in (204, 304) else int(rng.lognormvariate(7, 1.5))
            latency = round(min(rng.lognormvariate(3, 1), 60000.0), 3)
            rec: dict[str, object] = {"ts": ts, "method": rng.choice(METHODS), "path": path, "status": status,
                                      "bytes": size, "latency_ms": latency}
            if rng.random() < 0.001:
                rec = bad(rec, rng)
            lat = rec["latency_ms"]
            lat_text = format(lat, ".3f").rstrip("0").rstrip(".") if isinstance(lat, float) else str(lat)
            fc.write(f"{rec['ts']},{rec['method']},{rec['path']},{rec['status']},{rec['bytes']},{lat_text}\n")
            fj.write(json.dumps(rec, separators=(",", ":")) + "\n")


if __name__ == "__main__":
    main()
