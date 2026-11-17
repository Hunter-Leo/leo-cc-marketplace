# Two-Layer State Machine

> Two layers: mission (the overall task) and work unit (the smallest verifiable unit).
> Both layers must be judged by **scripts**, not by the LLM deciding "which step we are at now" on its own.
> This table mirrors `scripts/flow.sh`; when the two disagree, the script is authoritative.

## 1. Mission Layer

```text
planning → gate → executing → reviewing → verified
    any state ───────────────────────────→ blocked   (terminal)
```

| State | Meaning | Exit condition |
|---|---|---|
| `planning` | requirements, grading, decomposition, role cards | plan and acceptance criteria persisted |
| `gate` | waiting for user confirmation (`../../spec-coding-team-skill/references/essence.md` I-3 hard gate) | user explicitly gives `confirmed`; can only be initiated by the lead to the user |
| `executing` | work units execute in parallel | every unit is `approved`, `merged`, `verified`, or `blocked` |
| `reviewing` | integration verification + acceptance | every acceptance criterion has evidence |
| `verified` | success terminal | `blocked` only if a later human decision invalidates the run |
| `blocked` | terminal; a human decision is required | `flow.sh recover` moves it to `planning` or `executing` |

Disallowed transitions (rejected by `flow.sh transition`):

- `planning → executing` (skipping the gate)
- `gate → verified` (no execution)
- `gate → planning` (rework happens inside `planning` before the gate, not by rolling back)
- Any backward move not listed below, and anything out of `blocked` (terminal)

## 2. Work Unit Layer

```text
pending → in_progress → for_review → approved → merged → verified
                ↑             │
                │             └→ changes_requested
                └──────────────────┘   only while failures < 3

any state → blocked   (terminal; recover with flow.sh reopen)
```

| State | Criterion | Who can set it |
|---|---|---|
| `pending` | lane declared, owner assigned, input paths exist, no write conflict | lead |
| `in_progress` | a claim is held (see team-invariants T-3) | executor |
| `for_review` | artifact persisted + return contains a verdict; the transition releases the claim | executor |
| `approved` | Adversary gives PASS, no blocker in findings | Adversary |
| `merged` | artifact has entered the integration branch, and build/full test suite passes | lead or integration script |
| `verified` | every acceptance criterion has evidence, executed by a **non-author** | Verifier |
| `changes_requested` | Adversary gives FAIL, at least one finding with severity ≥ major; increments `failures` | Adversary |
| `blocked` | a human decision is required | lead or human |

## 3. approved ≠ merged ≠ verified

Conflating these three is the most expensive mistake in a team process: it makes "review passed" look like "done".

| State | Evidence requirement | Where the artifact is | Who can overturn |
|---|---|---|---|
| **approved** | Adversary's PASS + zero blocker findings | still on the author's branch/workspace | the Adversary itself (upon discovering new evidence) |
| **merged** | integration branch contains the change + build and full test suite pass | integration branch | integration test failure |
| **verified** | every acceptance criterion mapped to command + output + `file:line`, executed by a non-author | integration branch | change of acceptance criteria |

Three independent gates:

- approved only means "the approach and implementation hold for the Adversary", not that it can be merged.
- merged only means "technically merged in", not that it meets the user's needs.
- verified only means "the acceptance criteria are met", not long-term quality.

**Any state design that merges these three into a single `done` will silently lose evidence somewhere.**

## 4. Transition Tables

### Mission

| Current | Allowed next | Precondition |
|---|---|---|
| `planning` | `gate` | `plan.md` and acceptance criteria exist |
| `planning` | `blocked` | human decision required |
| `gate` | `executing` | user `confirmed` persisted, and records the inquirer = lead |
| `gate` | `blocked` | user declines, or a human decision is required |
| `executing` | `reviewing` | every unit ∈ {approved, merged, verified} or blocked |
| `executing` | `blocked` | human decision required |
| `reviewing` | `verified` | all acceptance criteria have evidence |
| `reviewing` | `blocked` | a human decision is required |
| `verified` | `blocked` | a later human decision invalidates the run |
| `blocked` | — | terminal; only `flow.sh recover` moves out |

### Work unit

| Current | Allowed next | Precondition |
|---|---|---|
| `pending` | `in_progress` | the unit has an owner; claim taken |
| `pending` | `blocked` | human decision required |
| `in_progress` | `for_review` | artifact path exists and is non-empty; return contains a verdict; the transition releases the claim |
| `in_progress` | `blocked` | human decision required |
| `for_review` | `approved` | verdict=PASS and no blocker in findings |
| `for_review` | `changes_requested` | verdict=FAIL or a blocker exists; increments `failures` |
| `for_review` | `blocked` | human decision required |
| `changes_requested` | `in_progress` | `failures < 3`; a corresponding finding has been assigned to the executor |
| `changes_requested` | `blocked` | `failures >= 3` or human decision required |
| `approved` | `merged` | integration branch build + full test suite pass |
| `approved` | `blocked` | human decision required |
| `merged` | `verified` | non-author executes acceptance, evidence complete |
| `merged` | `blocked` | human decision required |
| `verified` | `blocked` | a later human decision invalidates the unit |
| `blocked` | — | terminal; only `flow.sh reopen` moves out |

Illegal examples (must be rejected by the script): a `pending` unit cannot jump straight to `approved`; an `in_progress` unit cannot jump straight to `merged`; an `approved` unit cannot jump straight to `verified`; a `merged` unit cannot roll back to `changes_requested`; an `in_progress` unit cannot roll back to `pending`.

## 5. Recovery

- `flow.sh reopen --unit <id> --reason <text>` moves **any** unit state back to `pending`. It refuses when `unit.failures >= 3` unless `--force true` is given after a recorded user decision.
- `flow.sh recover` releases a stale claim and moves `mission=blocked` to `planning` (no units) or `executing` (units exist). It does not reopen units; use `reopen` for that.
- Neither subcommand is available to teammates as an escape hatch: recovery follows a human decision and is recorded in the event log.

## 6. Why Scripts Rather Than an LLM

| Risk | LLM behavior | Script behavior |
|---|---|---|
| state judgment | advances early based on "feels almost done" | only recognizes preconditions |
| step skipping | fabricates reasonable justification for skipping | no such ability |
| same input | may give different judgments across rounds | deterministic |
| audit | cannot prove the judgment process afterward | replayable |
| concurrency | two agents may both think they are the current advancer | file lock / single writer |

The LLM may **suggest** the next step (`next_action`), but **setting** can only be done by scripts. Only after this boundary is drawn can the state machine be trusted.

## 7. Connection with the Return Contract

Each return's `verdict` directly drives the transition:

```text
verdict=PASS    → for_review → approved (still needs findings check)
verdict=FAIL    → for_review → changes_requested
verdict=BLOCKED → current state → blocked (then recover or reopen)
```

The verdict must also be persisted to `.team/<run>/verdicts/<unit-id>.json` with at least `{verdict, artifacts, stop_reason}`; the `SubagentStop` hook blocks conversation-only returns.

Therefore: **a return without a verdict is not allowed to enter any transition**. This is an L3-layer constraint (enforcement-ladder.md), not a suggestion.
