# Phase 07 — Execution Loop

> This file contains the Execution Loop, Deviation Protocol, tasks.md update rules, and Requirement Complete checklist. Read this after completing Part 1-3 of `00-start-and-resume.md`.

**Entry:** `start-and-resume.md` + `execution-plan.md` exist.
**Exit:** All tasks reach `done`, `.dev/blueprint.md` updated.

---

## 4.1 Phase B Execution Discipline

> These rules apply to ALL agents entering Phase B. Every agent MUST read this before starting the first task.

#### Hard Rules

1. **Read start-and-resume.md before execution** — every agent MUST read its Constitution, Coding Reference, Git Workflow, and this Phase B Execution Discipline before any work. If resuming: run Session Bootstrap first.

2. **Read spec-coding-skill SKILL.md** — every agent MUST read the master SKILL.md for full methodology, state machine, and deviation protocol.

3. **Follow the execution loop** — the 12-step loop below must be followed for each task. No skipping or merging.

4. **Follow code standards** — OOP/SOLID, type annotations, consistent naming. See [../shared/01-oop-principles.md](../shared/01-oop-principles.md) and [../shared/02-coding-standards.md](../shared/02-coding-standards.md).

5. **Follow comment standards** — every public class, function, and file must have a docstring. See [../shared/02-coding-standards.md](../shared/02-coding-standards.md) § Documentation.

6. **Follow Git standards** — branch naming, commit format, pre-commit checks. See [../shared/03-git-workflow.md](../shared/03-git-workflow.md).

7. **Never implement implicit fallback** — prohibited at ALL levels:
   - No silent catch and return default
   - No hidden retry masking transient failures
   - No log-and-continue past real errors
   - No silent fallback to a less correct implementation
   - Always follow the Deviation Protocol: log to issues.md, assess severity, present to user

8. **Integration tests must not mock internal code or external dependencies** — mock only at system boundaries (network, time, randomness, third-party APIs unavailable in test env). See [../shared/02-coding-standards.md](../shared/02-coding-standards.md) § Testing Philosophy.

9. **Scan local environment for tools, skills, and methods** — check available skills, MCP tools, and agent types from session context. Apply relevant [methods](../references/methods/) via Method Selection at Phase 07 entry.

#### Execution Loop Reminder

Before starting the loop, the agent has:
- [x] Passed the A→B Gate (docs confirmed, branch created)
- [x] Created and confirmed `execution-plan.md`
- [x] Read `00-start-and-resume.md` including Phase B Execution Discipline
- [x] Read spec-coding-skill SKILL.md

---

## 4.2 Execution Loop

> ## STOP — Before You Write Any Code
>
> For **every task**, complete these checks before writing a single line:
>
> | # | Check | Skip Consequence |
> |---|-------|------------------|
> | 1 | Read `plan.md` for this task's approach | Wrong design |
> | 2 | Read `init.md § Constitution` | Violate OOP/SOLID |
> | 3 | Read affected source files (in sections if large) | Reimplement or break callers |
> | 4 | Evaluate [Vertical Slice TDD](../references/methods/01-vertical-slice-tdd.md) trigger | Miss TDD when applicable |
> | 5 | Confirm correct feature branch (`git branch --show-current`) | Commit to wrong branch |
>
> **After implementing**, complete the [Self-Check](../shared/00-agent-execution.md#self-check-after-each-task) before marking done.

Repeat for each task in `generated/rounds/round-[NNN]/tasks.md` — never skip steps or batch tasks.

**Pre-loop:** Determine round number from Round History, then:
- Read [01-round-mechanism.md](01-round-mechanism.md) for state machine and decision matrix
- Read `generated/rounds/round-[NNN]/tasks.md` for the current task list
- Read `issues.md` for any open issues from previous rounds
- When resuming a round, re-read Deviation Protocol and Round History

```
0.  Confirm feature branch exists:
      git branch --show-current
      If not on feature branch (should not happen after A→B Gate):
      → STOP. Return to Phase A→B Gate.

1.  Mark task as `in-progress` in tasks.md

2.  Read the current round's `plan.md` and relevant generated docs

3.  Read all affected source files (in sections if large)

4.  Read standards + Method Selection:
      a. init.md § Constitution
      b. Vertical Slice TDD evaluation — does this task have a clear,
         stable public interface?
         - Yes: Use RED → GREEN → REFACTOR micro-cycles per behavior.
           Replace steps 5-9 below with the TDD cycle.
         - No: Record justification and proceed.
      c. OOP/SOLID, coding standards, git conventions

5.  Implement the minimal change needed

    ---
    ⚠ DEVIATION CHECK (run after EVERY implementation step)
    Did anything differ from plan.md or tasks.md?

    | Severity | Action |
    |----------|--------|
    | Low (variable rename, helper extraction) | Continue. Note in commit. |
    | Medium (bug in unrelated code, new tool needed) | Log to issues.md (open). Continue. |
    | High (plan infeasible, interface must change) | STOP. Log to issues.md. Set task blocked. Present options to user. |

    Forbidden: silently modifying plan.md, adding unplanned files, changing interfaces without logging.
    ---

6.  Verify code against standards:
      [ ] SOLID principles followed
      [ ] Type annotations on all parameters/returns
      [ ] New file has module-level docstring
      [ ] New class has class-level docstring
      [ ] New public function has full docstring
      [ ] No hardcoded secrets
      [ ] No linting errors
      [ ] No circular imports

7.  Write tests:
      [ ] Normal cases covered
      [ ] Edge cases covered
      [ ] Error/exception cases covered

8.  Run all tests — existing + new — all must pass

9.  Update tasks.md:
      a. Set status to `done`
      b. Write implementation summary in Notes (note any deviation)

10. Pre-commit check:
      [ ] All tests pass
      [ ] No linting errors
      [ ] No hardcoded secrets
      [ ] Docstrings complete
      [ ] Unnecessary files not staged
      [ ] On correct feature branch
      [ ] Commit message: ≤72 chars, imperative, English

11. Commit:
      git add <specific files>
      git commit -m "[NNN] T-XXX <type>: <imperative summary ≤ 72 chars>"

12. If interactive mode: show summary, ask before proceeding.
```

> After step 11, repeat from step 0 for the next task.

---

## 4.3 Deviation Protocol

> The most common violation is silently fixing problems instead of logging them. Read this before starting.

**Authority:** This section handles *how* to handle deviations. The state machine in [01-round-mechanism.md](01-round-mechanism.md) tells *which* state to transition to.

**Rule: never silently modify plan.md, add unplanned files, or change interfaces without going through this protocol.**

#### Severity Levels

| Severity | When | Action |
|----------|------|--------|
| **Low** | Detail differs (variable naming, helper extraction, minor refactor) | Adjust directly. Note in commit. No round impact. |
| **Medium** | Bug in unrelated code, small new tool not in plan | Log to issues.md (open). Continue current task. |
| **High** | plan.md design infeasible, interface contract must change, dependency incompatible | STOP. Log to issues.md. Set task blocked. Present options. |

If unsure about severity, treat as HIGH.

#### High Severity Protocol

1. **STOP** — do not continue until decision is made
2. **Record** — write to both `issues.md` and `generated/rounds/round-[NNN]/issues.md` with type, severity, evidence, suggested fix
3. **Generate options** — use the appropriate template. Always include a recommendation.

**Template: plan-deviation** (plan.md design infeasible):
```
Option A: Update plan.md, fix within current round
    → Use: contained change, no cross-module ripple
    → Cost: restart task, update plan.md, adjust tasks.md
Option B: Log issue, defer to Round N+1 (recommended)
    → Use: significant design or cross-module changes needed
    → Cost: current task blocked; rest of round continues
Option C: Rollback, restart with different approach
    → Use: current approach fundamentally wrong, no clear path
    → Cost: lost work on task, clean slate
```

**Template: discovered-bug** (bug in unrelated code):
```
Option A: Log to TODO.md, continue (recommended)
    → Use: bug doesn't affect current requirement
    → Cost: none; tracked cross-requirement
Option B: Fix in current round
    → Use: bug blocks task or is trivially small
    → Cost: extends round by 1-2 tasks
```

**Template: scope-creep** (unplanned work discovered):
```
Option A: Add to current tasks.md (recommended)
    → Use: small, user confirmed priority
    → Cost: slightly extends round
Option B: Log to issues.md, plan for Round N+1
    → Use: significant work, priority unconfirmed
    → Cost: deferred
```

**Template: technical-contradiction** (plan assumed something the codebase doesn't support):
```
Option A: Update plan + ADR documenting the resolution (recommended)
    → Use: contained contradiction, clear resolution path
    → Cost: restart task, update plan.md, create ADR
Option B: Log issue to Round N+1
    → Use: significant re-design needed, current round cannot absorb
    → Cost: current task blocked; rest of round continues
Option C: Escalate to architecture review
    → Use: cross-module impact, fundamental architecture question
    → Cost: pause round until architecture review completes
```

4. **Present to user**:
   ```
   ⚠ [type] — [one-line summary]

   **Found in:** T-XXX — [task name]
   **Description:** [what was discovered]

   **Options:**
   1. Option A: [title] (recommended) — [rationale]
   2. Option B: [title] — [rationale]

   Please choose, or suggest another approach.
   ```
5. **Wait for decision** — user picks one; if no response after 5 min, mark the task as `blocked` and ask again. Do NOT auto-execute without explicit user confirmation.
6. **Execute** — implement decision, update tasks.md / plan.md

#### Mid-Round New Tasks

If a small new task is needed within the current round (user confirms, or low severity):
1. Stop current task at a clean checkpoint
2. Add the new task to tasks.md (status: `not-started`, Notes explaining why)
3. Resume current task or switch to new based on dependencies

Do not execute an unplanned task without recording it in tasks.md first.

#### Issues vs TODO.md

- `issues.md` — execution problems within the requirement that affect plan/task fidelity
- `.dev/TODO.md` — cross-requirement out-of-scope discoveries

#### If an issue is logged to BOTH files

If the same item appears in both issues.md and TODO.md:
1. Keep it in the file aligned with its source round (issues.md for in-round deviations, TODO.md for out-of-scope discoveries)
2. Remove the duplicate from the other file
3. Add a cross-reference in Notes: "Cross-ref: also logged to TODO.md (removed)"

---

## 4.4 tasks.md Update Rules

Every update to tasks.md must include:
1. **Status change** — not-started → in-progress → done / blocked
2. **Implementation summary** in Notes — what was actually done, especially if it deviated from plan.md

Example for a completed task:
```
Implemented using Strategy pattern instead of planned if/elif chain.
Added UserScoreCache class not in original plan — required for performance.
All 12 tests pass.
```

---

## 4.5 Requirement Complete — Round End

When all tasks reach `done` (or runnable tasks are `blocked`):

1. **Finalize round issues** — update `generated/rounds/round-NNN/issues.md`: set each entry to resolved / open / wontfix. Open entries remain in `issues.md` for cross-round tracking.

2. **Check `issues.md`** — read all open issues and summarize for the user

3. **Cross-requirement dependency check:** Read `.dev/blueprint.md` and `.dev/TODO.md`. If this requirement's completion unblocks another requirement (dependency satisfied), update the blocked requirement's Status in blueprint.md and notify the user.

4. **Write Round Summary** — update `start-and-resume.md § Round History`:
   ```
   ### Round [N] (complete)
   - **Status:** ✅ done (or ⏸ blocked)
   - **Tasks:** X planned, Y completed, Z deferred
   - **New issues:** ISS-NNN, ISS-MMM
   - **Summary:** What this round achieved.
   ```

5. **Update `.dev/blueprint.md`** — set Round, Phase, Status. See [../shared/05-blueprint-management.md](../shared/05-blueprint-management.md).

6. **Method Selection — Dual-Axis Review:** Significant round with substantial new code?
   - **Yes**: Apply [Dual-Axis Review](../references/methods/02-dual-axis-review.md). Two parallel reviews (standards + spec). Both must pass.
   - **No**: Record justification. Step 11 self-check checklist suffices.

7. **If no open issues:** declare complete, create PR/merge (step 9):
   > ✅ All tasks complete for [NNN]-[req-name]. Summary: X tasks, Y deviations. No open issues.

8. **If open issues remain:** notify user:
   > ✅ Round N complete. X/Y tasks done. Open: ISS-NNN, ISS-MMM.
   > Start Round N+1? I'll read issues.md, update plan.md and tasks.md incrementally.
   > Or reply **no** to finish.

   If user confirms Round N+1, proceed to Phase 01* (see [01-round-mechanism.md](01-round-mechanism.md) § Phase 01*).

9. **Create a pull request or local merge** using the format in [../shared/03-git-workflow.md](../shared/03-git-workflow.md). For PRs: `gh pr create --title "..." --body "..."`. For local merge: `git checkout main && git merge --no-ff ...`.

#### User Abandons Mid-Round

When a user stops the current round before all tasks are complete:
1. Mark all in-progress tasks as `blocked` with notes on what was attempted
2. Round summary: current completed count / total, blocked count
3. Update `.dev/blueprint.md`: set Status to `⏸ mid-round pause`
4. Preserve round artifacts (tasks.md, plan.md, issues.md) for resume
5. On resume: Session Bootstrap will detect the mid-round state and prompt the user
