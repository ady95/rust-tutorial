#!/usr/bin/env bash
# 07-4: Claude Code 에게 stats.py 를 Rust 로 이식하게 한다 (WSL·Linux)
# 사용법 (ch07/floats 에서): bash run_port.sh <실행이름> <원본 기록 폴더>
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
NAME="$1"; RAW="$2"
WS="$HOME/work/ch07_runs/$NAME"
rm -rf "$WS"; mkdir -p "$WS" "$RAW"
cp -r "$HERE/task/." "$WS/"
(cd "$WS" && python3 make_cases.py)
mkdir -p "$WS/.claude" && cp "$HERE/settings.json" "$WS/.claude/settings.json"
cd "$WS"
start=$(date +%s)
claude -p "python_src/stats.py 를 Rust 로 이식해 주세요. AGENTS.md 를 따르세요." \
  --output-format stream-json --verbose \
  --permission-mode acceptEdits --strict-mcp-config \
  --allowedTools "Bash(cargo *)" "Bash(python3 compare.py*)" \
  --max-turns 60 --max-budget-usd 5 > "$RAW/$NAME.jsonl"
echo "claude exit=$? wall=$(( $(date +%s) - start ))s"
python3 - "$RAW/$NAME.jsonl" <<'EOF'
import json, sys
for line in open(sys.argv[1], encoding="utf-8"):
    e = json.loads(line)
    if e.get("type") == "result":
        print({k: e.get(k) for k in ("subtype", "num_turns", "duration_ms", "total_cost_usd")},
              "denials", len(e.get("permission_denials") or []))
EOF
OUT="$HERE/runs/$NAME"; rm -rf "$OUT"; mkdir -p "$OUT"
cp -r rust_app/src rust_app/Cargo.toml "$OUT/" 2>/dev/null
cp reports/port_report.md "$OUT/" 2>/dev/null
cargo build -q --release --manifest-path rust_app/Cargo.toml && python3 compare.py | tail -1
