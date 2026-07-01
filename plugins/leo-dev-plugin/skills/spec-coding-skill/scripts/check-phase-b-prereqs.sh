#!/usr/bin/env bash
# check-phase-b-prereqs.sh — Check Phase B prerequisites
# Run after Phase A→B Gate user confirmation, before entering Execution Loop
set -euo pipefail

REQ_NAME="${1:-}"

if [ -z "$REQ_NAME" ]; then
    echo "[FAIL] Usage: ./scripts/check-phase-b-prereqs.sh <NNN-req-name>"
    echo "[INFO] Example: ./scripts/check-phase-b-prereqs.sh 001-user-auth"
    exit 1
fi

echo "=== Phase B Prerequisites Check ==="
echo "Requirement: $REQ_NAME"
echo ""

CURRENT=$(git branch --show-current 2>/dev/null)
if [ "$CURRENT" = "main" ] || [ "$CURRENT" = "master" ]; then
    echo "[FAIL] Still on $CURRENT — feature branch was not created in Phase A→B Gate"
    exit 1
else
    echo "[PASS] On feature branch: $CURRENT"
fi

BASE=".dev/$REQ_NAME"

if [ ! -d "$BASE" ]; then
    echo "[FAIL] .dev/$REQ_NAME/ does not exist — Phase A not completed"
    exit 1
fi
echo "[PASS] Requirement directory: $BASE"

[ -f "$BASE/init.md" ] && echo "[PASS] init.md" || { echo "[FAIL] init.md missing"; exit 1; }
[ -f "$BASE/issues.md" ] && echo "[INFO] issues.md exists (round > 1)" || echo "[INFO] issues.md will be created during execution"

GEN="$BASE/generated"
[ -f "$GEN/start-and-resume.md" ] && echo "[PASS] start-and-resume.md" || { echo "[FAIL] start-and-resume.md missing — Phase 06 not completed"; exit 1; }

LATEST_ROUND=$(ls -d "$GEN/rounds/round-"*/ 2>/dev/null | sort -t- -k2 -n | tail -1)
if [ -n "$LATEST_ROUND" ]; then
    RNAME=$(basename "$LATEST_ROUND")
    [ -f "${LATEST_ROUND}plan.md" ] && echo "[PASS] $RNAME/plan.md" || echo "[FAIL] $RNAME/plan.md missing"
    [ -f "${LATEST_ROUND}tasks.md" ] && echo "[PASS] $RNAME/tasks.md" || echo "[FAIL] $RNAME/tasks.md missing"
else
    echo "[FAIL] No rounds directory found — Phase 04/05 not completed"
    exit 1
fi

echo ""
echo "[PASS] All Phase B prerequisites met — ready to begin Execution Loop"
