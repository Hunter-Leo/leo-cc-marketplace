#!/usr/bin/env bash
# validate-branch.sh — Check feature branch status for spec-coding-skill
set -euo pipefail

CURRENT=$(git branch --show-current 2>/dev/null)

if [ -z "$CURRENT" ]; then
    echo "[FAIL] Not in a git repository"
    exit 1
fi

if [ "$CURRENT" = "main" ] || [ "$CURRENT" = "master" ]; then
    echo "[FAIL] On $CURRENT branch — should be on a feature branch"
    exit 1
fi

if ! echo "$CURRENT" | grep -qE '^(feat|fix|refactor|test|docs|style|perf|ci|build|chore)/'; then
    echo "[WARN] Branch '$CURRENT' does not match naming convention: <type>/<description>"
    echo "[INFO] Expected examples: feat/001-user-auth, fix/002-payment-timeout"
else
    echo "[PASS] Branch '$CURRENT' follows naming convention"
fi

if [ -d ".dev" ]; then
    echo "[PASS] .dev/ directory exists"
else
    echo "[WARN] No .dev/ directory — project not initialized with spec-coding-skill"
fi

if [ -n "$(git status --porcelain 2>/dev/null)" ]; then
    echo "[WARN] Uncommitted changes detected — run git status to review"
else
    echo "[PASS] Working tree is clean"
fi

echo ""
echo "--- Branch Summary ---"
echo "Branch: $CURRENT"
git log --oneline -3 2>/dev/null || true
