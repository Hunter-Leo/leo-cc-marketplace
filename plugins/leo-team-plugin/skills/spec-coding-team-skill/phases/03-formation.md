# N3 Formation — Team formation and work-unit splitting

> Goal: turn `tasks.md` into a mechanically schedulable `generated/team-plan.md`: each unit has a unique owner, a unique write set, and a unique acceptance command.
> Prerequisite: `flow.json.mission=gate`; the branch has been created; `primer.md` has been written.
> This phase writes only `team-plan.md` and `.team/<run>/prompts/`; it does not spawn executors and does not write business code. It also mutates runtime state by running `add-unit`, `transition --to executing`, and `checkpoint`.

## Step 1 — Read tasks.md and count task types

Read `tasks.md § Task Table` line by line, count by type:

| `tasks.md` type | Meaning | Owner |
|---|---|---|
| `implementation` | production code changes; `owned_files` must include its test files | executor |
| `verification` | independent review, acceptance evidence collection; **does not write unit tests** | reviewer |
| `research` | external fact research; done here if not completed in N1 | science-researcher |

Count and write into `team-plan.md § Statistics`:

```markdown
- implementation: <n> tasks / <m> files
- verification: <n> tasks
- research: <n> tasks
- Modules involved: <list>
- Shared files: <index/router/types/config/schema/migration etc.>
```

**Hard rule**: writing unit tests and integration tests belongs to `implementation` and must stay in the executor unit. Stripping tests into a separate role or unit is forbidden.

## Step 2 — Split implementation work units by owned_files

Unit definition: the write set + acceptance command that one executor completes in one `claim`. IDs use `U-01..U-nn`.
`flow.json.units` **registers implementation units only**; reviewer / science-auditor verification tasks are covered in Step 2b.

### Splitting rules (all hard rules)

1. Each unit's `owned_files` is non-empty and lists **exact paths**; new files must be written with full paths, and broad globs covering undetermined files are forbidden.
2. An implementation unit has at most 5 files and net changes ≤200 lines; split if exceeded.
3. When splitting, test files must be in the same unit as the code they cover.
4. Shared mutable files (`index.*`, `router.*`, `types.*`, global config, schema, migration) **may have only one owner**; other units consume them via interfaces and must not co-edit.
5. Each implementation unit's owner must be an executor; tests must not be stripped into a separate unit or role.
6. Each unit must have an `acceptance`: a directly executable command.
7. Once unit IDs are finalized, they must not be reused or reordered.

| ID | Owner | Archetype | owned_files | depends_on | acceptance |
|---|---|---|---|---|---|
| U-01 | spec-executor | Builder | `src/a.ts`, `tests/a.test.ts` | none | `npm test -- a` |
| U-02 | spec-executor | Builder | `src/b.ts`, `tests/b.test.ts` | U-01 | `npm test -- b` |

## Step 2b — Verification arrangement (not in flow.units)

reviewer / auditor work is a phase responsibility and is not registered as an implementation unit:

| ID | Owner | Artifact | depends_on | acceptance |
|---|---|---|---|---|
| V-01 | spec-reviewer | the `## Round N — spec-reviewer — <unit-id>` section of `generated/findings.md` | all `for_review` units | one section per unit, with verdict + evidence |
| V-02 | spec-science-auditor | `generated/science-audit.md` | auditable artifacts complete | Verdict line present |

## Step 3 — Verify the write sets are pairwise disjoint

For each pair `(Ui, Uj)` in the unit table, do:

1. Expand `owned_files`: for existing files, verify existence with `git ls-files`; for new files, compare by literal path.
2. Compute the intersection. **Empty intersection → pass.**
3. Non-empty intersection → try in order:
   - **Merge**: combine the two units into one, keep one owner; if file count >5 or line count >200, go to 4.
   - **Ownership uniqueness**: assign the shared file to one unit, remove it from the other unit's `owned_files` and change that unit to `depends_on`.
   - **Serialization**: if it still cannot be eliminated, keep both units as-is but mark `execution: serial`, and they must not be `claimed` at the same time.
4. If after serialization there remains a case where "the same file must be edited by two roles at the same time" → mark `risk: high`, write into `team-plan.md § High Risk`, and state it explicitly to the user at Step 6.
5. **Mechanical recheck**: after unit registration is complete, run `bash "${CLAUDE_PLUGIN_ROOT}/scripts/check-lanes.sh"`.
   - exit 0 (OK/WARN) → pass; WARN requires item-by-item manual confirmation and must be written into `team-plan.md § Scheduling Decision`.
   - exit 1 (definite overlap exists) → must return to step 3 and re-split; must not enter Step 6.

Prohibitions:

- Forbidden to let two units co-write one file on the grounds of "different features".
- Forbidden to copy a shared file into two copies and modify each separately.
- Forbidden to turn overlapping units into parallel ones without recording it.

### Scheduling facts

The flow script has only one global claim: only one write is allowed at a time. `owned_files` being disjoint is a condition for **allowing scheduling**, not permission to "write simultaneously". Parallel benefit comes from: read-only analysis overlapping with implementation, and verification roles overlapping with the next unit; writes are serialized by claim.

## Step 4 — Choose roles (default 2–3, cap 4)

### Role selection table

| Task composition | Required | Optional (when not covered in N1) | Size |
|---|---|---|---|
| Pure code implementation | spec-executor ×1 + spec-reviewer ×1 | spec-explorer | 2–3 |
| Code + unfamiliar module | spec-executor + spec-reviewer | spec-explorer | 3 |
| Code + interface/architecture uncertainty | spec-executor + spec-reviewer | spec-architect (requires `inspect.md`) | 3 |
| Code + `auditor=true` | + spec-science-auditor | — | 3 |

Count implementation + verification roles only: 1 executor + 1 reviewer + (auditor ? 1 : 0) + (explorer re-spawned in N3 because it was not covered in N1 ? 1 : 0) + (architect re-spawned for the same reason ? 1 : 0). The N1 researcher is not counted because it is not re-spawned in N4. Cap 4.

### Role constraints (hard-coded)

- executor has at most 1 instance; the same role must not run in parallel at any time; multiple code units are handled serially by the same executor.
- reviewer has at least 1; when `science_gate.auditor=true`, science-auditor has at least 1 and is irreplaceable.
- when `science_gate.researcher=true`, researcher has at least 1.
- every selected role must have ≥1 task (implementation unit or verification arrangement); idle roles without tasks must be removed.
- role count cap 4 (including auditor). Over 4 → cut architect, then explorer; must not cut auditor.
- when both switches are false, spawning researcher / auditor is forbidden.
- when `auditor=true` and `researcher=false`, `science-audit.md` must cite existing in-project evidence; otherwise auditor will be `BLOCKED` due to the missing `research.md`. PM must record the evidence path in `decisions.md`, or switch to D.

## Step 5 — Write team-plan.md

### Required global sections

| Section | Required content |
|---|---|
| `## Run` | <run> / round / branch / base_ref / phase_a_confirmed / time |
| `## Science gate` | researcher / auditor booleans, owner, artifacts, status |
| `## Statistics` | statistical results from Step 1 |
| `## Team` | roles, instance count, archetype, live phases |
| `## Unit Table` | implementation unit table from Step 2; verification arrangement as a separate table |
| `## Verification Arrangement` | reviewer / auditor tasks, artifacts, dependencies from Step 2b |
| `## Scheduling Decision` | implementation order, read-only overlap arrangement, write-set conflict handling, `bash "${CLAUDE_PLUGIN_ROOT}/scripts/check-lanes.sh"` result |
| `## Checkpoints` | one CP per 3 units; what is checked and the action when it fails |
| `## High Risk` | serial/shared-file risks; write `none` when empty |
| `## Confirmation` | write `pending` on submission; after confirmation backfill the user's original text, time, `sha256(team-plan.md)` |

### Required fields per unit (five elements)

Use `### U-<nn> — <title>` as the unit; a missing field makes it incomplete:

| Field | Criterion |
|---|---|
| `Objective` | one sentence, mapping to a `tasks.md` task ID and at least 1 AC |
| `Output` | exact artifact paths + report back per `rails.md` R-10 |
| `Source guidance` | required reading file paths + section/line ranges + reading order; "refer to the relevant code" is forbidden |
| `Scope boundary` | explicitly "what not to do": which files not to change, which dependencies not to add, which interfaces not to touch |
| `owned_files` | exact path list; pairwise disjoint from other units |

Supplementary fields: `Owner`, `Archetype`, `depends_on`, `Definition of done` (including verification command), `Startup prompt` path.

### Startup prompt files

Write `.team/<run>/prompts/<unit>.md` for each unit; content must include: role definition, `owned_files`, Objective, Source guidance, Scope boundary, report-back contract (R-10). If the file does not exist → the unit must not start.

## Step 6 — Present, confirm, import state

PM submits the following summary (also giving the full `team-plan.md` path):

```markdown
## N3 Team Plan — [NNN] <requirement name>

- Team: <spec-role ×n, ...> (<2–4> roles total)
- Units: <n> (all serialized); read-only overlap: <n>
- Write lock: 1 at a time (the flow script's single claim)
- Checkpoints: every 3 units
- High risk: none | <listed one by one>
- science gate: researcher=<bool> / auditor=<bool>
- Detailed plan: .dev/<run>/generated/team-plan.md

Reply `confirmed` to start N4; to change roles or units, say directly what to change.
```

Confirmation semantics are the same as N2: only accept `confirmed` / "confirm execution" / "approve execution" in the user's own message; "okay" and "looks good" do not count. After confirmation:

1. Write the original text and time into `team-plan.md § Confirmation`.
2. For **each implementation unit**, run:

```bash
bash "${CLAUDE_PLUGIN_ROOT}/scripts/flow.sh" add-unit --id U-01 --owner spec-executor --files "src/a.ts,tests/a.test.ts"
```

`--files` is comma-separated and order-independent; new files use full paths. Verification arrangements (V-xx) are not written into `flow.json.units`. If `add-unit` reports a duplicate ID → stop; overwriting is forbidden.

3. Run `bash "${CLAUDE_PLUGIN_ROOT}/scripts/flow.sh" transition --to executing --by pm`.
4. `bash "${CLAUDE_PLUGIN_ROOT}/scripts/flow.sh" checkpoint --note "N3 confirmed; units loaded"`.

If the user requests role/unit changes → modify `team-plan.md` and resubmit for confirmation. If the final role count differs from the N2 submitted value, or the science gate booleans change → the N2 submission is void: stay at `gate`, revise and resubmit the N2 template, and obtain confirmation again. If a revision must happen in N1, use the legal rollback path (`bash "${CLAUDE_PLUGIN_ROOT}/scripts/flow.sh" transition --to blocked` → `bash "${CLAUDE_PLUGIN_ROOT}/scripts/flow.sh" recover` → `planning`) before resubmitting.

## Full example (condensed)

```markdown
# Team Plan — 001-auth-refresh

## Run
- run: 001-auth-refresh | round: 1 | branch: feat/001-auth-refresh
- base_ref: main @ a1b2c3d | phase_a_confirmed: yes

## Science gate
| Role | Required | Owner | Artifact | Status |
|---|---|---|---|---|
| researcher | false | - | research.md | skipped |
| auditor | true | spec-science-auditor | science-audit.md | pending |

## Statistics
- implementation: 4 tasks → 2 units / 8 files
- verification: 1 task
- research: 0 tasks
- Modules involved: auth, api
- Shared files: src/api/router.ts

## Team
| Role | Instances | archetype | Phase |
|---|---|---|---|
| spec-executor | 1 | Builder | N4–N6 |
| spec-reviewer | 1 | Reviewer | N4–N6 |
| spec-science-auditor | 1 | Verifier | N4–N6 |

## Unit Table
| ID | Owner | Archetype | owned_files | depends_on | acceptance |
|---|---|---|---|---|---|
| U-01 | spec-executor | Builder | src/auth/refresh-store.ts, tests/auth/refresh-store.test.ts | none | npm test -- refresh-store |
| U-02 | spec-executor | Builder | src/api/auth-refresh.ts, tests/api/auth-refresh.test.ts | U-01 | npm test -- auth-refresh |

## Verification Arrangement
| ID | Owner | Artifact | depends_on | acceptance |
|---|---|---|---|---|
| V-01 | spec-reviewer | Round 1 reviewer section of findings.md | U-01, U-02 | verdict + evidence per unit |
| V-02 | spec-science-auditor | science-audit.md | U-01 | final conclusion Verdict |

## Scheduling Decision
- Implementation order: all serialized — U-01/U-02 have the same owner and the flow script has a single claim; V-01/V-02 depend on the implementation units.
- Serial: U-01 → U-02 → V-01/V-02.
- Must not run in parallel: src/api/router.ts belongs to U-02; U-01 does not modify it.

## Checkpoints
| CP | After | Checked content | On failure |
|---|---|---|---|
| CP-1 | U-02 | npm test -- auth + refresh-store | stop, record in findings.md |
| CP-2 | V-01 | AC coverage + dual-axis review | return to changes_requested |
| CP-3 | V-02 | science-audit PASS | must not be verified |

## High Risk
- none

## Confirmation
- pending

### U-01 — refresh token storage and rotation
- Owner: spec-executor
- Archetype: Builder
- owned_files: src/auth/refresh-store.ts, tests/auth/refresh-store.test.ts
- Objective: implement persistence and one-time rotation, satisfying AC-1/AC-2
- Output: the two files above + R-10 report-back
- Source guidance: first read plan.md § Module/interface changes, then architecture-review.md § Data model, finally src/auth/token.ts:40-120
- Scope boundary: do not change src/api/router.ts; do not add dependencies; do not change the users table schema
- Definition of done: `npm test -- refresh-store` exit 0; negative rotation test passes
- Startup prompt: .team/001-auth-refresh/prompts/U-01.md
```

## Completion criteria

- All `§` sections of `team-plan.md` and the five required fields of each unit are complete.
- All units' `owned_files` are pairwise disjoint; overlapping items have been merged/uniquified/serialized and recorded.
- Role count 2–4; each role has ≥1 task (implementation unit or verification arrangement); the roles corresponding to the science gate are present.
- The user's `confirmed` has been written into `team-plan.md § Confirmation`.
- `flow.json.units` has been written by `add-unit`, `mission=executing`, and the checkpoint has been written.
