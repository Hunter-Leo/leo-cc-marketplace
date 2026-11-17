# N5 Round Review — Round review and closure

> Goal: use an independent context to determine whether this round can enter N6; if not, open Round N+1 within the same session.
> Prerequisite: `flow.json.mission=reviewing`; no claim; all implementation units are `for_review`/`approved`/`merged`/`verified`.

## 1. Inputs (missing any → BLOCKED)

| Input | Source | Purpose |
|---|---|---|
| `generated/findings.md` | each role's own section + PM summary section | unresolved findings, severity, accepted-debt records |
| `generated/science-audit.md` | science-auditor (required when `auditor=true`) | fact-assertion adjudication |
| `flow.json` | `bash "${CLAUDE_PLUGIN_ROOT}/scripts/flow.sh" status` | mission, round, unit states, failures |
| `git diff <base>..<HEAD>` | branch | fixed review point |

reviewer writes `## Round N — spec-reviewer — <unit-id>` in `findings.md`, with two sections inside the same section: `### Axis 1 — Standards/OOP` and `### Axis 2 — spec/acceptance`. The two sections gather evidence independently; merging verdicts or reordering severity is forbidden.

## 2. Decision table (PM mechanically aggregates; must not downgrade on its own)

First count: `B = number of blockers`, `C = number of criticals`, `M = number of majors not accepted by the user`, `A = science-audit verdict`.

| B | C | M | A | Decision |
|---|---|---|---|---|
| >0 | any | any | any | open Round N+1; must not enter N6 |
| 0 | >0 | any | any | open Round N+1; must not enter N6 |
| 0 | 0 | >0 | any | open Round N+1; the user may release after accepting majors as debt |
| 0 | 0 | 0 | FAIL | open Round N+1; incorrect fact conclusions must be fixed |
| 0 | 0 | 0 | UNVERIFIABLE | must not enter N6; an `UNVERIFIABLE` verdict never permits `verified` — only explicit user adjudication recorded in `decisions.md` can close it, and the audit file must then carry a `PASS` or a decision reference |
| 0 | 0 | 0 | PASS or auditor=false | enter N6 |

Only minor/nit → enter N6, and write unfixed items into `findings.md § Backlog` (non-blocking).

severity is assigned by reviewer / science-auditor. PM may only aggregate; downgrading must be `confirmed` by the user and written into `decisions.md`.

## 3. Opening Round N+1 (same session)

### Incremental principle

1. **Do not rewrite `plan.md`**. Return to N1/N2 only if the scope changes.
2. `tasks.md` only appends `## Round N+1 Increment`, new task IDs use `R<N>-U<k>`, and each writes `supersedes: <finding ID>`.
3. mission stays `reviewing`; do not attempt `reviewing → executing`.
4. Run `bash "${CLAUDE_PLUGIN_ROOT}/scripts/flow.sh" set --round <N+1>`, then `bash "${CLAUDE_PLUGIN_ROOT}/scripts/flow.sh" checkpoint --note "open round N+1"`.
5. Affected `approved`/`merged`/`verified` units: `bash "${CLAUDE_PLUGIN_ROOT}/scripts/flow.sh" reopen --unit <U-ID> --reason "<finding-id>"`, the unit returns to `pending`; then follow the normal flow `pending → in_progress`.
6. Affected `for_review` units: `bash "${CLAUDE_PLUGIN_ROOT}/scripts/flow.sh" transition --unit <U-ID> --to changes_requested`.
7. Newly created units (original unit `failures >= 3` or needs splitting): `bash "${CLAUDE_PLUGIN_ROOT}/scripts/flow.sh" add-unit --id <new-id> --owner <role> --files "<globs>"`, also write into `team-plan.md`, new IDs are not reused. Using `reopen` to wash a unit with `failures >= 3` back to `pending` to bypass user adjudication is forbidden — the script rejects it directly. Only after the user explicitly decides to continue may you run `bash "${CLAUDE_PLUGIN_ROOT}/scripts/flow.sh" reopen --unit <U-ID> --reason "<user adjudication text>" --force true`, and record it in `decisions.md`.
8. Previous-round findings sections must not be rewritten; append a new section for the new round. Append `D-xxx: round_opened` to `decisions.md`.

### Redispatch

- teammate still alive → send the new unit block via SendMessage, preserving its context.
- teammate already unresponsive → recover per section 4, re-spawn and inject the primer.
- the fix unit's `Source guidance` must include the corresponding finding's `file:line` and evidence paths.
- after fixing, must re-run that unit's `acceptance` + affected regression tests; running only the new tests is not enough.
- **after the fix unit's re-review returns PASS, PM must change the corresponding finding's Status to `fixed` (or `accepted`) with evidence.** Changing only the code but not the status will cause `check-team-complete.sh` to keep judging that finding as unclosed and block — this exact step was hit in rehearsal.
- `changes_requested → in_progress` rejected (`failures >= 3`) → split a new unit or user adjudication; resetting `failures` to bypass is forbidden.

### Round cap

| Condition | Action |
|---|---|
| round ≥ 3 and `B + C` has not decreased compared with the previous round | stop the automatic loop; user adjudication (continue / narrow scope / return to single agent / terminate) |
| the same finding appears in 2 consecutive rounds | determine that the root cause is not located; stop and report; do not open another round |
| no new valid findings within a round and only nit remains | determine gold-plating; force wrap-up and enter N6 |

Round escalation must carry evidence: `B/C/M` counts per round, finding ID changes, failure command output paths.

## 4. Cross-session interruption: degraded recovery

Trigger conditions (any): session ends/restarts; teammate has no liveness signal; `flow.json.claim` is non-empty but has no corresponding active agent.

### Hard rules

**Never assume the teammate is still alive.** Do not send a message to a non-existent session and then keep waiting; do not take a previous session's `PASS` directly as this round's evidence.

### Recovery order (fixed)

| Step | Action | Determination |
|---|---|---|
| 1 | Read `generated/dead-ends.md` | failed approaches must not be retried as-is; each `DE-xx` is a forbidden path; if absent, record and continue |
| 2 | Read `generated/handoff.md` + `bash "${CLAUDE_PLUGIN_ROOT}/scripts/flow.sh" status` + `findings.md` | confirm round, branch, claim, unresolved findings, next action |
| 3 | `git status --short --branch`; compare HEAD with the handoff record | inconsistent → stop and explain the difference |
| 4 | Re-run the baseline: full test command + `bash "${CLAUDE_PLUGIN_ROOT}/scripts/flow.sh" status` | if any fails, fix the environment first; must not start changing code |
| 5 | Release the stale claim: `bash "${CLAUDE_PLUGIN_ROOT}/scripts/flow.sh" recover` | no claim → output "no change"; when `mission=blocked`, recover to `planning`/`executing`, still requiring a user adjudication record |
| 6 | Update `handoff.md` | fixed fields per `templates/handoff.md`; missing fields make it invalid |
| 7 | Re-spawn as needed | spawn only one role at a time; the primer must be re-injected; the new session does not inherit old context |
| 8 | Continue the `in_progress` unit | the same owner continues; must not assume previous progress |
| 9 | Correct contradictory state | unit `lane` inconsistent with evidence → `bash "${CLAUDE_PLUGIN_ROOT}/scripts/flow.sh" reopen --unit <U-ID> --reason "missing evidence"`, and record in `decisions.md` |

### handoff.md must contain

`resumption_prompt`, state snapshot (round/branch/HEAD/uncommitted/last passing test), pending items (open issues / next_action / do_not_redo / blocked_on), expiry policy. Template at `templates/handoff.md`.

### Degrading to subagent or single agent

Choose B/C per `references/degradation.md`:

1. Write `decisions.md`: `trigger: degrade_mode`, with reason, completed verification evidence, user confirmation.
2. Keep `.team/<run>/flow.json`, `findings.md`, `dead-ends.md`, `handoff.md`; must not delete the audit chain.
3. subagent mode: report back to `.team/<run>/verdicts/<unit>.json`, N3 cancels read-only overlap, everything serialized.
4. single-agent mode: continue from the current branch and `handoff.md`; already `verified` parts are not redone, unverified parts are re-run per the single-agent flow.

## Completion criteria

- The decision table lands on a single conclusion and is written into `findings.md § Round <N> Conclusion` (PM section).
- Entering N6: no unresolved blockers; when the auditor is enabled, `science-audit.md` has no `FAIL`, and any `UNVERIFIABLE` verdict has been closed by explicit user adjudication recorded in `decisions.md`, with the audit file carrying a `PASS` or a decision reference.
- Opening N+1: `flow.json.round` has been incremented, affected units have been `reopen`ed to `pending` or moved to `changes_requested`, or new units have been added; the checkpoint has been written.
- Cross-session recovery: `handoff.md` has complete fixed fields, baseline commands pass, stale claim released.
