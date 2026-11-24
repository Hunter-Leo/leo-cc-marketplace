#!/usr/bin/env bash
# Append one event to evals/results/raw/events.jsonl
# usage: log_event.sh RUN_ID TASK_ID MODE EVENT ACTOR [META_JSON]
set -euo pipefail

RUN_ID=${1:?run_id}
TASK_ID=${2:?task_id}
MODE=${3:?mode}
EVENT=${4:?event}
ACTOR=${5:?actor}
META=${6:-'{}'}

EVALS="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="$EVALS/results/raw/events.jsonl"
mkdir -p "$(dirname "$OUT")"

python3 - "$OUT" "$RUN_ID" "$TASK_ID" "$MODE" "$EVENT" "$ACTOR" "$META" <<'PY'
import datetime, json, sys
out, run_id, task_id, mode, event, actor, meta = sys.argv[1:8]
try:
    meta = json.loads(meta) if meta else {}
except json.JSONDecodeError:
    meta = {"raw": meta}
rec = {
    "ts": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    "run_id": run_id,
    "task_id": task_id,
    "mode": mode,
    "event": event,
    "actor": actor,
    "meta": meta,
}
with open(out, "a", encoding="utf-8") as f:
    f.write(json.dumps(rec, ensure_ascii=False) + "\n")
PY
