#!/usr/bin/env bash
# validate-branch.sh — Check feature branch status for spec-coding-skill
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib/common.sh"

CURRENT=$(current_branch)

if [ -z "$CURRENT" ]; then
    die "Not in a git repository"
fi

if is_default_branch "$CURRENT"; then
    die "On $CURRENT branch — should be on a feature branch"
fi

if ! echo "$CURRENT" | grep -qE '^(feat|fix|refactor|test|docs|style|perf|ci|build|chore)/'; then
    log_warn "Branch '$CURRENT' does not match naming convention: <type>/<description>"
    log_info "Expected examples: feat/001-user-auth, fix/002-payment-timeout"
else
    log_pass "Branch '$CURRENT' follows naming convention"
fi

if [ -d ".dev" ]; then
    log_pass ".dev/ directory exists"
else
    log_warn "No .dev/ directory — project not initialized with spec-coding-skill"
fi

if [ -n "$(git status --porcelain 2>/dev/null)" ]; then
    log_warn "Uncommitted changes detected — run git status to review"
else
    log_pass "Working tree is clean"
fi

echo ""
echo "--- Branch Summary ---"
echo "Branch: $CURRENT"
git log --oneline -3 2>/dev/null || true
