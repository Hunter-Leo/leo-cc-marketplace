# Tasks — [NNN]-[req-name]
**Round:** [N]

## Status Table

| ID | Type | Task Name | Status | Priority | Deps | Notes |
|---|---|---|---|---|---|---|
| T-001 | feat | Implement X | not-started | P0 | - | |
| T-002 | test | Unit tests for X | not-started | P0 | T-001 | |

**Status values:** `not-started` · `in-progress` · `done` · `blocked`

**Type values:** `feat` · `test` · `refactor` · `fix` · `docs` · `config` · `db` · `ui`

**Priority values:** `P0` blocker · `P1` core · `P2` nice-to-have

**Task naming:** `<imperative verb> <noun>` — e.g. "Implement user repository"

## Dependency Rules

- Add deps in the `Deps` column using `T-XXX` IDs
- Tasks with unmet deps stay `not-started` until all deps reach `done`
- Circular dependencies not allowed — split or redesign

## Task Details

### T-001 — Implement X

**Goal:** What this task achieves.

**Requirements:**
- Specific requirement 1
- Specific requirement 2

**Acceptance Criteria:**
- Unit tests pass
- Criterion 2

**References:** `plan.md § Implementation Path`, `src/module_a/service.py`

**Implementation Summary:** *(filled in when task reaches `done`)*

## Granularity Rules

- Each task completable in one focused session
- Implementation and its tests are **separate tasks** (T-001 implements, T-002 tests)
- Task modifying >2 files is probably too large — split it
- Tasks must respect the dependency order in `plan.md`

## Out of Scope

If you discover a bug or new requirement while working, log it to `.dev/TODO.md` — not to tasks.md.
