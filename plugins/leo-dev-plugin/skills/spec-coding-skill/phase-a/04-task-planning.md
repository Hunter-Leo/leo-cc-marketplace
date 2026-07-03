# Phase 05 — Task Planning

Produce the current round's `tasks.md` after its `plan.md` is complete. This document drives execution in Phase 07.

**Entry:** `plan.md` exists at `.dev/[NNN]-[req-name]/generated/rounds/round-NNN/plan.md`.
**Exit:** `tasks.md` created at `.dev/[NNN]-[req-name]/generated/rounds/round-NNN/tasks.md` with all tasks defined.

> **Per-round:** Each round has its own `tasks.md` under `rounds/round-NNN/`. For Round N+1, read `issues.md` and create a new `tasks.md` with tasks addressing open issues. Previous round's tasks.md stays as a historical record under its round directory.

Before writing `tasks.md`:
1. Read `plan.md` in full — tasks must map directly to the implementation path defined there
2. Read `init.md § Constitution` — ensure each implementation task has a corresponding test task as required by the constitution

## Output

`.dev/[NNN]-[req-name]/generated/rounds/round-NNN/tasks.md`

## Creating tasks.md

Read the template at `templates/tasks.md`, then create the tasks file at the path above. The template includes: Status Table, Dependency Rules, Task Detail blocks, Granularity Rules, and Out of Scope.

Before writing tasks.md:
1. Read `plan.md` in full — tasks must map directly to the implementation path
2. Read `init.md § Constitution` — ensure each implementation task has a corresponding test task

**ID format:** `T-001`, `T-002`, etc. (sequentially numbered, no gaps)

**Status values:** `not-started` · `in-progress` · `done` · `blocked`

**Type values:**

| Type | When to Use |
|------|-------------|
| `feat` | New feature, API endpoint, module, or component |
| `test` | Unit tests, integration tests, E2E tests |
| `refactor` | Code restructuring without behavior change |
| `fix` | Bug fix in existing code |
| `docs` | Documentation, comments, docstrings |
| `config` | Build config, CI/CD, tooling, dependencies |
| `db` | Database migration, schema change, seed data |
| `ui` | UI component, styling, layout |

**Priority values:** `P0` blocker · `P1` core · `P2` nice-to-have

**Task naming:** `<imperative verb> <noun>` — e.g. "Implement user repository"

## Task Granularity Rules

- Each task should be completable in one focused session
- Implementation task and its unit tests are **separate tasks** (T-001 implements, T-002 tests)
- A task that modifies more than two files is probably too large — split it
- Tasks must respect the dependency order defined in `plan.md`

---

## Out-of-Scope Items

If you discover a bug or new requirement while working on a task, do **not** add it to `tasks.md`. Log it to `.dev/TODO.md` instead — see [shared/00-agent-execution.md](../shared/00-agent-execution.md) for the format and rules.

## After Completing Phase 05

Update `.dev/blueprint.md`: advance this requirement's Phase to `05 Tasks` and Status to `✅ done` for this phase.
