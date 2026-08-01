#!/usr/bin/env bash
# check-dev-structure.sh — Validate .dev/ documentation tree
# Usage: check-dev-structure.sh [path]
#   path: .dev directory to check (default: .dev)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib/common.sh"

if [ "${1:-}" = "-h" ] || [ "${1:-}" = "--help" ]; then
    echo "Usage: check-dev-structure.sh [path]"
    echo "  Validate .dev/ documentation tree at the given path"
    echo "  Default: .dev/"
    exit 0
fi

BASE="${1:-.dev}"

if [ ! -d "$BASE" ]; then
    log_fail "No .dev/ directory found"
    log_info "Run spec-coding-skill Phase 01 to initialize"
    exit 1
fi

echo "=== .dev/ Structure Check ==="
echo ""

check_file "$BASE/blueprint.md" "blueprint.md exists" \
    FAIL "blueprint.md missing — project-level overview document" || true

for req in "$BASE"/[0-9][0-9][0-9]-*/; do
    [ -d "$req" ] || continue
    NAME=$(basename "$req")
    echo ""
    echo "--- $NAME ---"

    check_file "${req}init.md" "init.md" FAIL "init.md missing" "  " || true
    check_file "${req}issues.md" "issues.md" \
        INFO "issues.md missing (created during execution)" "  " || true
    check_file "${req}generated/start-and-resume.md" "start-and-resume.md" \
        INFO "start-and-resume.md missing (created in Phase 06)" "  " || true

    for round in "${req}generated/rounds/round-"*/; do
        [ -d "$round" ] || continue
        RNAME=$(basename "$round")
        echo "  $RNAME:"
        check_file "${round}plan.md" "plan.md" FAIL "plan.md missing" "    " || true
        check_file "${round}tasks.md" "tasks.md" FAIL "tasks.md missing" "    " || true
    done
done

echo ""
echo "=== Check Complete ==="
