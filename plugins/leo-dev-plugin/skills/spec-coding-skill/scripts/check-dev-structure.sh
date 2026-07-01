#!/usr/bin/env bash
# check-dev-structure.sh — Validate .dev/ documentation tree
set -euo pipefail

BASE=".dev"

if [ ! -d "$BASE" ]; then
    echo "[FAIL] No .dev/ directory found"
    echo "[INFO] Run spec-coding-skill Phase 01 to initialize"
    exit 1
fi

echo "=== .dev/ Structure Check ==="
echo ""

if [ -f "$BASE/blueprint.md" ]; then
    echo "[PASS] blueprint.md exists"
else
    echo "[FAIL] blueprint.md missing — project-level overview document"
fi

for req in "$BASE"/[0-9][0-9][0-9]-*/; do
    [ -d "$req" ] || continue
    NAME=$(basename "$req")
    echo ""
    echo "--- $NAME ---"

    [ -f "${req}init.md" ] && echo "  [PASS] init.md" || echo "  [FAIL] init.md missing"
    [ -f "${req}issues.md" ] && echo "  [PASS] issues.md" || echo "  [INFO] issues.md missing (created during execution)"
    [ -f "${req}generated/start-and-resume.md" ] && echo "  [PASS] start-and-resume.md" || echo "  [INFO] start-and-resume.md missing (created in Phase 06)"

    for round in "${req}generated/rounds/round-"*/; do
        [ -d "$round" ] || continue
        RNAME=$(basename "$round")
        echo "  $RNAME:"
        [ -f "${round}plan.md" ] && echo "    [PASS] plan.md" || echo "    [FAIL] plan.md missing"
        [ -f "${round}tasks.md" ] && echo "    [PASS] tasks.md" || echo "    [FAIL] tasks.md missing"
    done
done

echo ""
echo "=== Check Complete ==="
