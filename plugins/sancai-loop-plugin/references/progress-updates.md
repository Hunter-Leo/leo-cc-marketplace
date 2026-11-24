# Progress Updates (execution-time reporting)

> This is the part `leo-team-plugin` was missing: update state continuously during execution, not only at the end.

## Principles

1. **Write state to disk**, not only into the conversation.
2. **Append on every change**; never rewrite history.
3. **Humans see aggregates**, not raw logs.
4. **Never describe "in progress" as "done".**

## Files

```text
.sancai/runs/<run>/
├── L2-harness/progress.md   # human-readable progress
├── L2-harness/run.json      # current state
└── audit/events.jsonl       # machine event stream
```

### progress.md format

```markdown
## WO-001 — <title>

- [x] read intent
- [x] inspect src/a.ts
- [ ] implement rotation
- [ ] run acceptance
- [ ] report

Last update: 2026-11-18T10:21:00Z
```

Rules:

- Only append/check off; never delete history.
- Each item is a verb phrase.
- When blocked, write `BLOCKED: <reason>` and include the evidence path.

### events.jsonl

Written by the harness / executor, never by hand:

```json
{"ts":"...","run":"001-x","event":"wo_started","meta":{"wo":"WO-001"}}
{"ts":"...","run":"001-x","event":"file_written","meta":{"path":"src/a.ts"}}
{"ts":"...","run":"001-x","event":"acceptance_run","meta":{"exit_code":0}}
{"ts":"...","run":"001-x","event":"wo_reported","meta":{"verdict":"PASS"}}
```

## When to update

Update at these moments:

- Work Order starts
- Every completed file or logical step
- Every acceptance run
- Every escalation
- Work Order ends (PASS / FAIL / BLOCKED)
- Run state changes

## Display format

At execution start and after every state change, show:

```text
[Sancai] run=001-auth  state=executing  wo=WO-001
──────────────────────────────────────────────
✅ read intent
✅ inspect src/a.ts
▶  implement rotation
   run acceptance
   report
──────────────────────────────────────────────
```

Symbols:

- `✅` done
- `▶` in progress
- `⏸` waiting (human / dependency)
- `✗` failed / blocked

## Forbidden

- Updating only `run.json` without `progress.md` (humans cannot see it)
- Replacing status with "almost there" / "basically done"
- Marking an unrun test as passed
- Deleting failed attempts
