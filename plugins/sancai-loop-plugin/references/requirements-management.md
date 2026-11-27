# Requirements Management

Requirements span runs. A run's `intent.json` is a signed snapshot of the
accepted requirements that run covers — not the project's requirement list.

## Two ledgers

```
.sancai/project/
├── requirements.json   REQ-*  accepted, testable, plannable
├── backlog.json        TODO-* raw captures, including unrelated discoveries
└── blueprint.md        generated view; do not edit
```

The JSON files are the source of truth. The Markdown blueprint is derived by
`sancai_requirements.py blueprint`.

### TODO (raw capture)

A TODO records something someone noticed. It has no contract yet.

```text
pending ──► promoted     human promoted it into a REQ
   │  ▲
   │  └──── deferred     human postponed it, still promotable
   ├──────► deferred     human decided to postpone
   └──────► rejected     human decided not to do it
```

Fields: `id`, `title`, `type` (`bug` / `feature` / `improvement` /
`tech-debt` / `finding`), `priority` (`P0`–`P3`), `status`, `relation`
(`related` / `unrelated`), `source`, `notes`, `req`.

### REQ (accepted requirement)

A REQ has acceptance criteria and can be selected into an intent.

```text
proposed ──► accepted ──► verified
    │            │
    │            ├─────► deferred
    │            └─────► rejected
    └─────► rejected
```

`verified` is written only by the H3 closeout transaction, after the human
accepts the run. Closeout upgrades selected `accepted` REQs to `verified` only
after every selected REQ has verified Work Order coverage.

Fields: `id`, `title`, `status`, `priority`, `source` (the TODO it came from),
`acceptance[]`, `depends_on[]`, `notes`, `history[]`.

Items are never deleted; every transition appends to `history`.

## Who may do what

| Action | Actor | Command |
|---|---|---|
| capture a TODO | agent | `capture` |
| list / read | agent | `list`, `status`, `blueprint` |
| select accepted REQs into a run | agent | `select --run <run> --req REQ-…` |
| promote TODO → REQ | **human** | `promote TODO-… --acceptance …` |
| accept a REQ | **human** | `accept REQ-…` |
| defer / reject | **human** | `defer <id> --reason …`, `reject <id> --reason …` |

The capability table denies agents direct `promote`, `accept`, `defer`, and
`reject`. An agent that wants one of these must escalate; the human runs it.

### Ledger freeze during a run

The project ledger is authored during H1. From `executing` until the run is
accepted or abandoned, the ledger is frozen:

- `promote`, `accept`, `defer`, `reject`, and `blueprint` are refused.
- `capture` does not write the project backlog; it appends to the run-local
  staging file (`L2-harness/project-updates.json`).
- `select` only works while `planning` and the intent is unsigned.

Closeout is the single publish point. It applies staged TODOs, upgrades selected
REQs to `verified`, and regenerates the blueprint after the accept card is
consumed. A run abandoned before H3 leaves staged updates run-local.
See `closeout.md`.

## Run intent snapshot

`intent.json` gains two optional fields:

```json
{
  "revision": 2,
  "requirements": ["REQ-001", "REQ-002"]
}
```

- `requirements` may only contain `accepted` REQs with at least one AC.
- Selecting bumps `revision`. Re-selecting the same REQ still bumps it, so the
  snapshot hash changes and the intent must be re-signed.
- `select` is refused once the intent is signed.
- An intent **without** `requirements` is legacy: WOs need no `--req`.
- An intent **with** `requirements` forces every `add-wo --req` to name one of
  them. A WO without `--req` is refused; a REQ not in the snapshot is refused.

H3 acceptance walks the snapshot: every selected REQ must have at least one
`verified` or `merged` WO bound to it, otherwise acceptance is refused with
`requirement has no verified work order: REQ-…`.

## Capture points

| Moment | Action |
|---|---|
| H1, human states the goal | If an `accepted` REQ already covers it, `select`. If not, capture a TODO and ask the human to `promote` + `accept`; do not self-promote. If the project has no ledger, legacy intent is allowed. |
| executing, related discovery | `capture --relation related`; it stages a run-local TODO and may become a REQ later. |
| executing, unrelated discovery | `capture --relation unrelated`; stage it and continue. Do not touch the current intent. |
| H3, major finding deferred | `accept --disposition defer:<WO-ID>` stages a `finding` TODO sourced to `run:<run>/WO:<WO-ID>`. It does **not** create a follow-up WO in the accepted run. |
| after a run | The human triages the backlog: `promote`, `defer`, or `reject`. |

A TODO never mutates an intent by itself. Only `select` writes the snapshot,
and only while the run is `planning` and the intent is unsigned.

## Why capture instead of action

- An accepted run must stay a closed contract. Adding work orders after
  acceptance reopens a terminal state and defeats the H3 gate.
- Unrelated work belongs to the project, not to this run. The backlog is where
  it waits without silently expanding scope.
- Promotion is a human decision because it creates a testable contract.

## Commands

```bash
python3 scripts/sancai_requirements.py init
python3 scripts/sancai_requirements.py capture \
  --title "..." --type feature --priority P2 \
  --source run:001-x --relation unrelated
python3 scripts/sancai_requirements.py list [--status pending] [--json]
python3 scripts/sancai_requirements.py promote TODO-001 \
  --acceptance '["API returns 200 for a valid token"]'
python3 scripts/sancai_requirements.py accept REQ-001
python3 scripts/sancai_requirements.py defer REQ-001 --reason "waiting on API"
python3 scripts/sancai_requirements.py reject TODO-002 --reason "duplicate"
python3 scripts/sancai_requirements.py select --run 001-x --req REQ-001
python3 scripts/sancai_requirements.py blueprint
python3 scripts/sancai_requirements.py status --json
```

`--acceptance` accepts a JSON array, a file path, or a newline-separated list.
Entries may be strings or objects with `text` / `expect`, and an optional `id`.

## Backward compatibility

- Existing runs and intents without `requirements` keep working.
- `add-wo` records no `req` for a legacy intent and accepts no `--req`.
- H3 coverage is empty for a legacy intent; all existing accept checks still
  apply.
- Old accepted runs gain no backlog entries until a new H3 defer runs.

## Phase 2 (not implemented)

Change requests while `executing` (re-sign the intent), dependency-aware
planning, milestones, and a signed triage card. Phase 1 stops at
capture + promote + select + coverage + closeout publication.
