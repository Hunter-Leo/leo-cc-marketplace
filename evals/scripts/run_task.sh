#!/usr/bin/env bash
# Run one eval task under one mode.
# usage: run_task.sh --task T.json --mode A|B|C [--runner manual] [--run-id ID] [--auto-accept]
set -euo pipefail

TASK=""; MODE=""; RUNNER="manual"; RUN_ID=""; AUTO_ACCEPT="false"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --task) TASK="$2"; shift 2 ;;
    --mode) MODE="$2"; shift 2 ;;
    --runner) RUNNER="$2"; shift 2 ;;
    --run-id) RUN_ID="$2"; shift 2 ;;
    --auto-accept) AUTO_ACCEPT="true"; shift ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
  esac
done

[[ -n "$TASK" && -n "$MODE" ]] || {
  echo "usage: run_task.sh --task T.json --mode A|B|C [--runner manual] [--run-id ID] [--auto-accept]" >&2
  exit 2
}
[[ "$MODE" =~ ^[ABC]$ ]] || { echo "mode must be A, B, or C" >&2; exit 2; }
[[ -f "$TASK" ]] || { echo "task not found: $TASK" >&2; exit 2; }

EVALS="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TASK_ID="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["id"])' "$TASK")"
RUN_ID="${RUN_ID:-$(date +%Y%m%d-%H%M%S)-$MODE}"
RUN_DIR="$EVALS/results/runs/$RUN_ID"
mkdir -p "$RUN_DIR"

echo "[eval] task=$TASK_ID mode=$MODE run=$RUN_ID"
bash "$EVALS/scripts/setup_task.sh" "$TASK" "$RUN_DIR"

bash "$EVALS/scripts/log_event.sh" "$RUN_ID" "$TASK_ID" "$MODE" start human '{}'
bash "$EVALS/scripts/log_event.sh" "$RUN_ID" "$TASK_ID" "$MODE" agent_start agent '{}'

set +e
bash "$EVALS/runners/$RUNNER.sh" "$RUN_DIR" "$TASK" "$MODE" "$RUN_ID"
RUNNER_RC=$?
set -e
if [[ $RUNNER_RC -ne 0 ]]; then
  bash "$EVALS/scripts/log_event.sh" "$RUN_ID" "$TASK_ID" "$MODE" runner_error "$RUNNER" "{\"rc\":$RUNNER_RC}"
fi

bash "$EVALS/scripts/log_event.sh" "$RUN_ID" "$TASK_ID" "$MODE" agent_end agent '{}'

set +e
python3 "$EVALS/scripts/check_ac.py" "$TASK" "$RUN_DIR" > "$RUN_DIR/ac.out" 2>&1
AC_RC=$?
set -e
cat "$RUN_DIR/ac.out"

if [[ -f "$RUN_DIR/ac.json" ]]; then
  META="$(python3 - "$RUN_DIR/ac.json" <<'PY'
import json, sys
d = json.load(open(sys.argv[1], encoding="utf-8"))
print(json.dumps({
    "ac_passed": d.get("ac_passed", 0),
    "ac_total": d.get("ac_total", 0),
    "hidden_passed": d.get("hidden_passed", 0),
    "hidden_total": d.get("hidden_total", 0),
    "success": d.get("success", False),
}))
PY
)"
else
  META='{"ac_passed":0,"ac_total":0,"success":false}'
fi

if [[ "$AUTO_ACCEPT" == "true" ]]; then
  DECISION="accept"
else
  read -r -p "[eval] accept this result? [y/N] " ans
  if [[ "$ans" =~ ^[Yy]$ ]]; then DECISION="accept"; else DECISION="abort"; fi
fi

if [[ "$DECISION" == "accept" ]]; then
  bash "$EVALS/scripts/log_event.sh" "$RUN_ID" "$TASK_ID" "$MODE" accept harness "$META"
else
  bash "$EVALS/scripts/log_event.sh" "$RUN_ID" "$TASK_ID" "$MODE" abort human "$META"
fi

echo "[eval] done. ac_rc=$AC_RC decision=$DECISION"
