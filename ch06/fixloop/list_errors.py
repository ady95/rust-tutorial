"""cargo build 의 json 진단에서 오류 코드·위치·메시지·수정 제안의 적용 가능성을 뽑는다 (06-2).

사용법 (크레이트 폴더에서): python3 list_errors.py
"""

import json
import subprocess

proc = subprocess.run(
    ["cargo", "build", "--message-format", "json"],
    capture_output=True,
    text=True,
)
for line in proc.stdout.splitlines():
    msg = json.loads(line)
    if msg.get("reason") != "compiler-message":
        continue
    diag = msg["message"]
    if diag["level"] != "error" or not diag["code"]:
        continue
    span = next(s for s in diag["spans"] if s["is_primary"])
    fixes = [
        s["suggestion_applicability"]
        for child in diag["children"]
        for s in child["spans"]
        if s["suggested_replacement"] is not None
    ]
    print(diag["code"]["code"], f"{span['file_name']}:{span['line_start']}", diag["message"], fixes)
