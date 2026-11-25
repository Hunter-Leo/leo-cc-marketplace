#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

if ! command -v claude >/dev/null 2>&1; then
  echo "claude CLI not found" >&2
  exit 1
fi

echo "claude $(claude --version 2>/dev/null | awk '{print $1}')"
mkdir -p evals/results

claude plugin eval . \
  --trust-plugin \
  --scaffold \
  --model "${EVAL_MODEL:-claude-sonnet-5}" \
  --judge-model "${EVAL_JUDGE_MODEL:-claude-haiku-4-5}" \
  --threshold "${EVAL_THRESHOLD:-0.8}" \
  --ablation none \
  --json evals/results/aggregate.json \
  "$@"
