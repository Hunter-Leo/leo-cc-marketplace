# H3 closeout transaction

Project state changes exactly once per run: after the human accepts H3. During
planning, the PM may author requirements. From `executing` until the run is
terminal, the project ledger is read-only and all discoveries are staged
run-locally.

## Files

```text
.sancai/project/requirements.json          source of truth
.sancai/project/backlog.json               source of truth
.sancai/project/blueprint.md               generated view

.sancai/runs/<run>/L2-harness/
  project-baseline.json                    ledger hashes captured planning→executing
  project-updates.json                     staged TODOs during the run
  closeout/plan.json                       frozen closeout plan
  closeout/journal.json                    crash-recovery journal
  closeout/lock                            O_EXCL closeout lock
```

## Ledger freeze

| Run state | Project ledger |
|---|---|
| `planning` | `capture`, `promote`, `accept`, `defer`, `reject`, `blueprint` allowed; `select` only while unsigned |
| `executing`, `integrating`, `reviewing` | read-only; `capture` stages; other mutations refused |
| `accepted`, `abandoned` | normal project commands allowed |

`init` is refused while any active run exists. The planning→executing transition
records `project-baseline.json`; H3 refuses to publish over external drift.

## Staging

`L2-harness/project-updates.json`:

```json
{
  "schema_version": 1,
  "run": "001-test",
  "todos": [
    {"stage_id": "STAGE-001", "title": "…", "type": "finding",
     "priority": "P2", "relation": "related",
     "source": "run:001-test/WO:WO-001", "notes": "…"}
  ],
  "requirements": [],
  "updated_at": "…"
}
```

Staged TODOs appear in `todos_for_run` with `status: "staged"` and
`staged: true`, so status views and graph items see them without publishing.
Final `TODO-*` ids are allocated only at closeout. An abandoned run leaves
staged data run-local.

## Accept sequence

```text
validate accept phrase/session/state
  → validate integration evidence, gates, verdicts, findings, baseline
  → build closeout plan (selected accepted REQs, staged TODOs, H3 deferral)
  → verify plan effect hash against the accept card's closeout_sha
  → acquire closeout lock
  → write closeout/plan.json
  → journal authorized {plan_sha, effect_sha, card_id, payload, args}
  → consume accept card
  → journal card_consumed
  → apply requirements / backlog / blueprint idempotently
  → journal project_applied
  → write run accepted + outcome + captured_todos
  → journal run_accepted
  → clear active run
  → append findings_acknowledged / outcome_accepted
  → journal committed
  → release lock
```

The `closeout_sha` in the accept card covers only the pre-disposition base plan
(selected requirements, staged TODOs, integration evidence, blueprint flag). H3
dispositions such as `defer:<FOLLOWUP-ID>` are supplied at accept time and
cannot invalidate a card generated earlier. The journal is the authority after
card consumption; `plan.json` is never rebuilt during resume, so TODO ids cannot
be reallocated.

## Resume

A crash after card consumption leaves the run `reviewing` with a journal.

```text
sancai_closeout.py status --run <run>
sancai_closeout.py resume --run <run>
```

Resume rules:

- `authorized` without `<card_id>.json.used` → refuse; the card was not consumed.
- `authorized` with the used marker → advance and continue.
- `card_consumed` or `project_applied` → replay the stored plan idempotently.
- already `accepted` → finish the journal only.
- abandoned → refuse.

The lock is O_EXCL. `resume --force` may clear a lock older than one hour.

## H3 dispositions

- `defer:<FOLLOWUP-ID>` stages a `finding` TODO; it does not create a WO in the
  accepted run.
- `waive:<reason>` records the acknowledgement without a TODO.
- blocker/critical findings still refuse acceptance.

## Guarantees and limits

- The project ledger is published once, after the human accept card is consumed.
- Partial multi-file writes are not filesystem-atomic; the journal makes them
  replayable and idempotent.
- Baseline drift is detected when a planning-time marker exists. Legacy runs
  without the marker skip that check.
- Closeout is a same-user guardrail, not a sandbox.
