# N6 Verification — Integration acceptance

> Goal: advance "review passed" to an auditable "merged and accepted".
> Prerequisite: N5 determination has no unresolved items; `flow.json.mission=reviewing`; all implementation units have `for_review`/`approved`.
> The three states must be reached in the order `approved → merged → verified`; skipping steps or combining declarations is forbidden.

## 1. Three-state determination (unit level + mission level)

### approved (review passed)

| Condition | Determination method |
|---|---|
| reviewer `verdict: PASS` | the last verdict in the corresponding unit section of `findings.md` |
| `blocker == 0 && critical == 0 && unaccepted_major == 0` | PM section counts in `findings.md` |
| when `auditor=true`, `science-audit.md` has no `FAIL`, and any `UNVERIFIABLE` has been closed by explicit user adjudication in `decisions.md`, with the audit file carrying a `PASS` or a decision reference | Verdict line and check matrix |
| minor/nit already in Backlog | `findings.md § Backlog` |

Issued by reviewer / science-auditor; PM only aggregates. PM's self-assessed PASS does not count as approved.
Unit action: `bash "${CLAUDE_PLUGIN_ROOT}/scripts/flow.sh" transition --unit <U-ID> --to approved`.

### merged (in the integration branch)

| Condition | Determination method |
|---|---|
| branch merged into the target branch | `git merge --no-ff <branch>` succeeds, or PR status is `MERGED` |
| no conflicts | merge command exit 0 |
| target branch HEAD contains the merge commit | `git merge-base --is-ancestor <branch> <target>` exit 0 |
| tests pass after merge | run the full test suite on the merged HEAD, exit 0 |

Executor: the user, or a PM with explicit user authorization. Teammates must not push or merge to trunk (R-8).
Approved evidence must exist before merging; merging directly without approval → process failure.
Unit action: `bash "${CLAUDE_PLUGIN_ROOT}/scripts/flow.sh" transition --unit <U-ID> --to merged`.

### verified (acceptance evidence complete)

| Condition | Determination method |
|---|---|
| every AC has evidence | AC IDs in `findings.md § PM — Verification Summary` correspond one-to-one with `init.md` |
| deletion-type requirements pass negative invariants | see section 4 |
| full tests pass on the merged HEAD | command + exit 0 + pass count |
| `check-team-complete.sh` outputs `OK` | see section 5 |
| working tree clean | `git status --porcelain` is empty (`.dev/`, `.team/` handled per project ignore rules) |

Unit action: `bash "${CLAUDE_PLUGIN_ROOT}/scripts/flow.sh" transition --unit <U-ID> --to verified`.
After all implementation units are verified: `bash "${CLAUDE_PLUGIN_ROOT}/scripts/flow.sh" transition --to verified`.

## 2. AC → evidence mapping

Append a table to the PM section of `findings.md`, exactly one row per AC:

| AC | Type | Evidence | Location | Result |
|---|---|---|---|---|
| AC-1 | automated | `npm test -- refresh-store` | `tests/auth/refresh-store.test.ts` | PASS |
| AC-2 | manual | five elements | `findings.md#ac-2` | PASS |

Rules:

- Using "the overall test suite passes" in place of per-AC mapping is forbidden.
- Automated evidence must state: test file path, test name, execution command, exit code.
- Manual evidence must state all five elements; missing one counts as unverified.
- Defect-fix ACs must additionally record: the command and output that reproduce the failure on the baseline commit, and the command and output that pass after the fix.

## 3. Five elements of manual evidence

| Element | Requirement | Counterexample |
|---|---|---|
| 1. Command/operation | directly copy-pasteable, or a step-by-step reproducible operation sequence | "clicked around manually" |
| 2. Precondition state | branch + HEAD, environment variables, fixtures, account/permissions | omits versions and data |
| 3. Input | the concrete request, file, args | "used some test data" |
| 4. Actual output | verbatim output, exit code, screenshot path; must not be rewritten | "result is normal" |
| 5. Determination | expected vs actual, conclusion PASS/FAIL | "looks fine" |

Template:

```markdown
### AC-<n> — <description>

- Command: <command>
- Precondition: branch=<branch>, HEAD=<sha>, env=<...>, fixture=<path>
- Input: <request/file/args>
- Actual output: <verbatim output or screenshot path> / exit=<code>
- Determination: expected <expected>; actual <actual>; conclusion PASS
```

## 4. Deletion-type requirements: negative invariants

When an AC includes "delete/decommission/remove/deprecate", you must also verify:

| Invariant | Determination |
|---|---|
| symbol absent | `rg "<symbol>" <source dir>` has 0 hits |
| entry point unreachable | the deleted HTTP route returns 404/410; the CLI flag reports unknown; the export no longer exists |
| contract synchronized | OpenAPI/schema/type definitions no longer contain the item |
| no silent fallback | old config keys are no longer read; defaults do not reintroduce the old behavior |
| consumers migrated | full typecheck / build / contract tests pass |

Example: delete `GET /api/v1/users/:id/legacy`

```markdown
### AC-5 (deletion type) — legacy endpoint decommissioned

- rg: `rg "users/:id/legacy|legacyEndpoint" src/` → 0 hits
- Request: `curl -i http://localhost:3000/api/v1/users/1/legacy` → HTTP/1.1 404
- Contract: openapi.yaml contains no `/api/v1/users/{id}/legacy`
- Fallback: `LEGACY_USER_API` config is no longer read (rg 0 hits)
- Regression: `npm test` → all pass
- Determination: PASS
```

Verifying only "the new feature works" without verifying "the old path truly disappeared" → that AC does not pass.

## 5. check-team-complete.sh

The script reads `.team/<run>/flow.json`, **always exits 0**, and the conclusion is in the output text: `OK` / `NOT COMPLETE` / `NO RUN`.

It can be run from any directory (it anchors to the repository root), so no `cd` is needed. Point it at the run explicitly when more than one run exists:

```bash
LEO_TEAM_DIR="<repo-absolute>/.team/<run>" \
  bash "${CLAUDE_PLUGIN_ROOT}/scripts/check-team-complete.sh"
```

The script mechanically checks:

| Check | Pass condition |
|---|---|
| mission | `mission=verified` |
| units | all implementation units `lane=verified` |
| researcher | when `science_gate.researcher=true`, `research.md` exists |
| auditor | when `science_gate.auditor=true`, `science-audit.md` exists and carries a `PASS` or a decision reference; an `UNVERIFIABLE` verdict never permits verification and is closed only by explicit user adjudication in `decisions.md` |

The script does not check AC coverage or the five elements; those two are verified manually (reproducibly) by reviewer and PM in sections 2–4.

Handling:

- Output `OK`: may report completion to the user.
- Output `NOT COMPLETE`: fix item by item; must not manually edit the script or delete `flow.json`.
- Output `NO RUN`: check `LEO_TEAM_DIR` and the run name; must not fabricate state.
- Blocked because mission is not verified: first complete unit verification and `transition --to verified`, then re-run.

## 6. Stop hook and PreCompact

The Stop hook (`validate-lane-write.sh --stop`) refuses to end when any of the following holds:

- `flow.json.mission != verified`;
- `science_gate.auditor=true` but `science-audit.md` cannot be found.

Rules:

- Must not bypass by deleting `flow.json`, changing `mission`, or skipping the hook.
- The script has no "abandon" allowlist; when incomplete, truthfully report the incomplete items to the user; must not fake `verified`.
- `stop_hook_active` is only used to prevent repeated interception, not as proof of completion.

The PreCompact hook requires a checkpoint no older than 30 minutes during `executing` / `reviewing`; run `bash "${CLAUDE_PLUGIN_ROOT}/scripts/flow.sh" checkpoint --note "pre-compact"` before compaction.

## 7. Execution order

1. N5 conclusion: no unresolved blockers.
2. PM advances the corresponding unit to `approved` based on reviewer's PASS.
3. After user authorization, merge the branch; run the full test suite on the merged HEAD.
4. Each approved unit → `merged`.
5. Build evidence for each AC one by one; add negative invariants for deletion-type; write into the PM section of `findings.md`.
6. Each merged implementation unit → `verified`.
7. All implementation units verified → `bash "${CLAUDE_PLUGIN_ROOT}/scripts/flow.sh" transition --to verified`.
8. Run `check-team-complete.sh`; only when it outputs `OK` may you wrap up.
9. Report to the user: branch, merge commit, test summary, AC coverage count, evidence paths.

## Completion criteria

- All three evidence sets approved / merged / verified are complete and reproducible.
- AC row count in `findings.md § PM — Verification Summary` == AC count in `init.md`.
- `check-team-complete.sh` outputs `OK`, and the output is saved.
- `flow.json.mission == verified`.
- The report to the user contains absolute paths to all evidence.
