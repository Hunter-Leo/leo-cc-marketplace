# Documentation Standard (Sancai)

> Documents are durable decisions, not process theater. Write only what a
> future reader needs to understand why the run exists, what was designed,
> what changed, and what remains open.

## Runtime vs durable

```text
.sancai/runs/<run>/        runtime and audit artifacts; never committed
docs/specs/<run-id>/       durable, distilled documents; committed
docs/adr/                  architecture decisions; committed
CHANGELOG.md               release history; committed
```

`.sancai/` is the raw event and evidence record. `docs/` is the curated record.
Do not commit both; promote only what survives the run.

## Five document types

| Document | When | Purpose |
|---|---|---|
| `intent.md` | Every run | Goal, non-goals, acceptance criteria, risk tier |
| `design.md` | M/L runs | Context, options, decision, interfaces, data model, test plan, rollback |
| `ADR-XXXX.md` | Irreversible/architecture/interface/data change | One decision and its consequences |
| `issues.md` | Every run with deviations | Plan deviations, discovered bugs, scope changes, contradictions |
| `acceptance.md` | Optional at H3 | What was accepted, evidence, open risks |

## Size matrix

| Size | intent | design | ADR | issues | acceptance |
|---|---|---|---|---|---|
| XS | required | not required | only if irreversible | if deviation | optional |
| S | required | short note | if interface/data change | if deviation | optional |
| M | required | required | if interface/data/irreversible | required | recommended |
| L | required | required + staged plan | required for cross-module decisions | required | required |

## Frontmatter

Every durable document starts with:

```yaml
---
id: SPEC-001
status: draft | approved | superseded
owner: <name>
last_updated: 2026-01-01
run_id: <run-id>
supersedes: <id or null>
---
```

## Required sections

### intent.md

- Goal: one sentence that determines success or failure.
- Non-goals: what this run will not do.
- Acceptance criteria: id, executable check, expected result.
- Risk tier: T0–T4 and the reason.
- Manual acceptance ratio: target 0%; hard maximum 20% with a written reason.
- Approver and approval timestamp.

### design.md

- Context: why this run exists and what constrains it.
- Options: at least two viable options, with tradeoffs.
- Decision: the chosen option and why.
- Interfaces: public functions, data shapes, error contracts.
- Data model: schema, IDs, migration, compatibility.
- Test plan: normal, edge, error, and integration cases.
- Rollback: how to undo the change.
- Risks: what could fail and how it is detected.

### ADR

- Status: proposed / accepted / superseded.
- Context: the forces at play.
- Decision: what was chosen.
- Consequences: what becomes easier and harder.
- Alternatives: what was rejected and why.

### issues.md

| Field | Meaning |
|---|---|
| `id` | `ISSUE-001` |
| `type` | `plan-deviation`, `discovered-bug`, `scope-creep`, `technical-contradiction`, `performance` |
| `severity` | `low`, `medium`, `high` |
| `status` | `open`, `resolved`, `deferred`, `waived` |
| `owner` | Who owns the resolution |
| `resolution` | What was done, or why it was deferred/waived |

Rules:

- Low: adjust and record.
- Medium: log an issue and continue only if it does not change acceptance.
- High: stop at H2 and present options.
- Never silently change the plan or an interface.

### acceptance.md

- Accepted Work Orders and their evidence hashes.
- Verifier verdict summary.
- Open issues and their disposition (`defer`, `waive`, `ack`).
- Residual risks and known limitations.

### CHANGELOG.md

Use Keep a Changelog. Each release lists:

- Version and date.
- Added / Changed / Fixed / Removed.
- Run IDs and evidence references.
- Breaking changes and migration notes.

## Rules

1. One fact, one place. Link instead of duplicating.
2. Update the document in the same Work Order as the code.
3. Do not commit `.sancai/` runtime artifacts.
4. Do not create a document for a decision that fits in one paragraph; put it in
   `design.md` or `issues.md`.
5. Do not use documents as a gate for XS/S runs; use them where they reduce risk.
6. All documents are English.

## G3 checklist

- [ ] `intent.md` has executable acceptance criteria and a risk tier.
- [ ] M/L runs have `design.md` with options, decision, interfaces, and rollback.
- [ ] Irreversible/interface/data decisions have an ADR.
- [ ] Deviations are in `issues.md` with severity and disposition.
- [ ] Documents match the code and evidence.
- [ ] No runtime artifact was committed.
