#!/usr/bin/env bash
# check-phase-b-prereqs.sh — Check Phase B prerequisites
# Run after Phase A→B Gate user confirmation, before entering Execution Loop
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib/common.sh"

REQ_NAME="${1:-}"

if [ -z "$REQ_NAME" ]; then
    log_fail "Usage: ./scripts/check-phase-b-prereqs.sh <NNN-req-name>"
    log_info "Example: ./scripts/check-phase-b-prereqs.sh 001-user-auth"
    exit 1
fi

echo "=== Phase B Prerequisites Check ==="
echo "Requirement: $REQ_NAME"
echo ""

CURRENT=$(current_branch)
if is_default_branch "$CURRENT"; then
    die "Still on $CURRENT — feature branch was not created in Phase A→B Gate"
else
    log_pass "On feature branch: $CURRENT"
fi

BASE=".dev/$REQ_NAME"

if [ ! -d "$BASE" ]; then
    die ".dev/$REQ_NAME/ does not exist — Phase A not completed"
fi
log_pass "Requirement directory: $BASE"

check_file "$BASE/init.md" "init.md" || exit 1
[ -f "$BASE/issues.md" ] && log_info "issues.md exists (round > 1)" || log_info "issues.md will be created during execution"

GEN="$BASE/generated"
check_file "$GEN/start-and-resume.md" "start-and-resume.md" \
    FAIL "start-and-resume.md missing — Phase 06 not completed" || exit 1

LATEST_ROUND=$(ls -d "$GEN/rounds/round-"*/ 2>/dev/null | sort -t- -k2 -n | tail -1)
if [ -n "$LATEST_ROUND" ]; then
    RNAME=$(basename "$LATEST_ROUND")
    check_file "${LATEST_ROUND}plan.md" "$RNAME/plan.md" FAIL "$RNAME/plan.md missing" || true
    check_file "${LATEST_ROUND}tasks.md" "$RNAME/tasks.md" FAIL "$RNAME/tasks.md missing" || true
else
    die "No rounds directory found — Phase 04/05 not completed"
fi

echo ""
log_pass "All Phase B prerequisites met — ready to begin Execution Loop"
