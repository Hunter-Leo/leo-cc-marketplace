#!/usr/bin/env bash
# Manual runner: human does the work in RUN_DIR/work.
# usage: manual.sh RUN_DIR TASK_JSON MODE RUN_ID
set -euo pipefail

RUN_DIR=${1:?run_dir}
TASK=${2:?task}
MODE=${3:?mode}
RUN_ID=${4:?run_id}

EVALS="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TASK_ID="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["id"])' "$TASK")"

echo
echo "============================================================"
echo " TASK : $TASK_ID"
echo " MODE : $MODE   (A=HITL, B=single agent, C=AITL)"
echo " WORK : $RUN_DIR/work"
echo "============================================================"
echo
echo "Do the task in the work directory. The harness will run AC afterwards."
echo

read -r -p "Press Enter when human work starts... " _
bash "$EVALS/scripts/log_event.sh" "$RUN_ID" "$TASK_ID" "$MODE" human_start human '{}'

read -r -p "Press Enter when human work / review is done... " _
bash "$EVALS/scripts/log_event.sh" "$RUN_ID" "$TASK_ID" "$MODE" human_end human '{}'

echo "[manual] finished."
