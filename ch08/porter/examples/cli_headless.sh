#!/usr/bin/env bash
# 08-1: 헤드리스 모드(claude -p)로 구조화된 결과 받기
# 사용법 (ch08/porter 에서): bash examples/cli_headless.sh ../projects/wordfreq
set -u
PROJECT="$1"
SCHEMA="$(cat "$(dirname "$0")/schema_functions.json")"
cd "$PROJECT"
claude -p "python_src/ 의 각 함수가 contracts/behavior_spec.md 의 어느 절을 구현하는지 정리해 주세요." \
  --output-format json --json-schema "$SCHEMA" \
  --model sonnet \
  --tools "Read,Glob,Grep" --allowedTools "Read,Glob,Grep" \
  --permission-mode dontAsk \
  --setting-sources "" --strict-mcp-config \
  --max-turns 10 --max-budget-usd 0.5 < /dev/null   # 표준 입력을 기다리지 않게
