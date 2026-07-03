# Phase 06 — Create start-and-resume.md / Phase 07 — Execution

> ## STOP — Are You Resuming an Interrupted Session?
>
> If returning after any interruption, run the [Session Bootstrap](#session-bootstrap) before doing anything else. Do not skip straight to a task.
>
> Quick self-check:
> - [ ] Read `.dev/blueprint.md` — overall project status
> - [ ] Read `issues.md` — any open issues from previous rounds
> - [ ] Read `tasks.md` — which task is next?
> - [ ] Read `init.md § Constitution` — design rules

**Entry (Phase 06):** `tasks.md` exists at `.dev/[NNN]-[req-name]/generated/tasks.md`.
**Exit (Phase 06):** `start-and-resume.md` created.
**Entry (Phase 06.5):** Phase A→B Gate confirmed.
**Exit (Phase 06.5):** `execution-plan.md` created at `generated/rounds/round-NNN/execution-plan.md`, user confirmed.
**Entry (Phase 07):** `start-and-resume.md` + `execution-plan.md` exist.
**Exit (Phase 07):** All tasks reach `done`, `.dev/blueprint.md` updated.

---

## Session Bootstrap

**When:** Entering an existing project with `.dev/` content (resuming after interruption).
**Action:** Bootstrap the session before any work.

1. **Check `.dev/blueprint.md`** — if missing, scan `.dev/` directories to reconstruct from existing `init.md` files, then inform the user
2. **Read** the blueprint and for each active or blocked requirement, read `tasks.md` for current task detail
3. **Present** full status to the user proactively:

   ```
   ## Project Status

   Blueprint: 3 requirements | ✅ Done: 1 | ▶ Active: 1 | ⏳ Idle: 1
   Backlog:   .dev/TODO.md has 2 unresolved items

   | Req | Phase | Status | Priority | Next Action |
   |-----|-------|--------|----------|-------------|
   | 001 user-auth | 07 Execution | ▶ in-progress | P0 | T-003: implement login |
   | 002 task-crud | 04 Plan | ⏳ pending | P1 | wait for 001 |
   | 003 collab    | 07 Done     | ✅ done    | P2 | shipped |

   **Recommended**: continue with 001-user-auth (T-003 is in-progress)
   ```

   Edge cases:
   - **All done**: "All requirements complete. Check `.dev/TODO.md` for backlog items."
   - **All blocked**: "All active requirements are blocked. See blocker notes below."
   - **Blueprint missing**: "No blueprint found. Scanned `.dev/` and found N requirements. Reconstructing blueprint..."

4. **Ask** the user which requirement to focus on, or proceed with the active one
5. **Open** `issues.md` for open issues (if round > 1)
6. **Open** `generated/rounds/round-[NNN]/tasks.md` and find the next unstarted task

> Do not skip to task execution without first showing the blueprint.

---

## Part 1: Phase 06 — Create start-and-resume.md

**Do not begin the execution loop until this file exists.**

Copy the template from `templates/start-and-resume.md` to `.dev/[NNN]-[req-name]/generated/start-and-resume.md`:

```bash
cp templates/start-and-resume.md .dev/[NNN]-[req-name]/generated/start-and-resume.md
```

The template includes: Quick Start, Resuming After Interruption, Session Bootstrap, Key Documents, Round History, Constitution, Git Workflow, and Phase B Discipline Reminder.

---

## Part 2: Phase A→B Gate — User Confirmation

> HARD GATE — Agent MUST NOT bypass or treat as advisory.
> Present all items in ONE message. User confirms ONCE; Agent creates branch and proceeds to Phase 06.5.

### Step 1 — Present Proposal

Template:
```
## Phase A Complete — Ready to Enter Phase B

All requirements documents are ready. Here's the summary:

**Documents produced:**
- ✅ `init.md` — scope, requirements, constitution
- ✅ `plan.md` — technical approach
- ✅ `tasks.md` — X tasks identified
- ✅ `start-and-resume.md` — execution guide (template copied)

**Branch:** `<type>/[NNN]-[req-name]` (auto-generated from requirement name)

**Next:** After confirmation, I will create the branch and proceed to Phase 06.5 Execution Planning — where I'll scan available agent types, draft an execution plan, and present sub-agent prompts for your review.

Reply **confirmed** to proceed, or tell me what to adjust.
```

### Step 2 — Process Confirmation

On user confirmation:
1. `git checkout -b <type>/[NNN]-[req-name]`
2. Update `.dev/blueprint.md`: set Status to `▶ in-progress`
3. Proceed to Phase 06.5

### Step 3 — Handle Change Requests

If changes requested: adjust, re-present the full proposal, wait for confirmation again.

> GATE RULE: "Looks good" without explicit confirmation is NOT sufficient. Ask: "Do you confirm? Reply **confirmed** to proceed."

---

## Part 3: Phase 06.5 — Execution Planning

> This phase runs AFTER the A→B Gate and BEFORE Phase 07. It produces `generated/rounds/round-[NNN]/execution-plan.md` — a per-round document defining execution mode, agent setup, and sub-agent startup prompts.

**Entry:** A→B Gate confirmed, branch created.
**Exit:** `execution-plan.md` created, user confirmed, Phase 07 ready.

### Step 0.5 — Execution Mode Recommendation

#### Default Mode (recommended for most projects)

When tasks.md shows a **sequential dependency chain**, the plan should follow this pattern:

1. **Execution Agent** (execution-capable model, e.g. Opus) — executes tasks in sequence, may batch simple tasks
2. **Review Agent** — reviews after each execution agent's batch
3. **Auto-advance** — proceeds without interactive pauses; blockers pause per Deviation Protocol

**OMC execution skills:** If oh-my-claudecode is available, consider using `oh-my-claudecode:ralph` or `oh-my-claudecode:ultrawork` to automate Phase B advancement.

#### Alternative Modes

**Step 1 — Check available execution skills from session context:**
- Read the list of available skills from the session context (system-reminder)
- Find execution-class skills (description mentions: autonomous execution, parallel agents, workflow automation, persistent loops)
- For each candidate, invoke the Skill tool to read its `Use_When` / `Do_Not_Use_When`

**Step 2 — Analyze `tasks.md`:**
- Total task count, type distribution
- Dependency structure (sequential vs parallel)

**Step 3 — Match** against `Use_When` conditions and recommend the best mode.

**Step 4 — If multi-agent mode (e.g. `/team`):**

a. Read available agent types from session context
b. Map tasks to roles with semantic naming: `executor-1`, `executor-2`, `designer-1`, `test-engineer-1` (forbidden: `worker-1`, `agent-2`)
c. Present team configuration:
   > Based on tasks.md (N tasks: X feature + Y test + Z UI), I recommend `/team`:
   > - `executor-1`, `executor-2` — T-001 ~ T-004
   > - `test-engineer-1` — T-005 ~ T-006
   > - `designer-1` — T-007
   >
   > Each worker reads `execution-plan.md` before their assigned tasks.
d. After Phase 06.5 execution-plan.md is confirmed, invoke the execution mode (e.g. `Skill(skill='oh-my-claudecode:team', ...)`) and instruct workers to read `execution-plan.md`.

> Rules: Agent role types come from session context — never hardcoded.

### Step 1 — Scan Available Agent Types

Read available agent types from session context (system-reminder). Identify candidates:

| Role | Search For |
|------|-----------|
| Execution agent | `executor`, `sonnet`, `opus`, or general-purpose types |
| Review agent | `code-reviewer`, `verifier`, or similar review-focused types |
| Specialists | `designer`, `test-engineer`, `debugger`, `scientist`, `security-reviewer` |

> Do not hardcode types. If no relevant types exist, fall back to single-agent mode.

### Step 2 — Analyze tasks.md

Read `generated/rounds/round-[NNN]/tasks.md`:
- Total task count, type distribution
- Dependency structure (sequential vs parallel groups)
- Determine optimal batching

### Step 3 — Draft Execution Plan

Read the template at `templates/execution-plan.md`, then create `.dev/[NNN]-[req-name]/generated/rounds/round-[NNN]/execution-plan.md` with:
- Selected agent types and roles
- Phase/milestone breakdown
- Full startup prompt text for EACH agent (must include the 7 document reading list)
- Review agent prompts must include "verify against execution loop and standards"

### Step 4 — Present to User

Show the execution plan with full startup prompt text for each agent, not just a summary.

Template:
```
> ## Execution Plan Draft — Ready for Review
>
> Created `execution-plan.md` at `.dev/[NNN]-[req-name]/generated/rounds/round-[NNN]/execution-plan.md`.
>
> **Mode:** [Dual Agent / Team / etc.]
> **Agent 1:** [type] — tasks T-001 ~ T-00X
> **Agent 2:** [type] — tasks T-00Y ~ T-00Z
> **Review checkpoints:** [after each stage / after all tasks]
>
> Each sub-agent's startup prompt instructs reading: shared/00-agent-execution.md, shared/02-coding-standards.md, shared/03-git-workflow.md, phase-b/00-start-and-resume.md § Execution Loop + § Phase B Execution Discipline, phase-b/01-round-mechanism.md, spec-coding-skill/SKILL.md
>
> Full prompts are in execution-plan.md. Reply **confirmed** to deploy, or tell me what to adjust.
```

### Step 5 — On Confirmation

1. Mark `execution-plan.md` status as `confirmed`
2. Update `.dev/blueprint.md`: set Phase `06.5 Execution Plan` → `done`, Phase `07 Execution` → `▶ in-progress`
3. Spawn sub-agents with their startup prompts (Skill tool for OMC modes, Agent tool for direct sub-agents)
4. Instruct each spawned agent to read `execution-plan.md` before their tasks
5. Enter Phase 07 Execution Loop

### Step 6 — On Change Requests

Adjust `execution-plan.md`, re-present the full proposal, wait for confirmation again.

### Edge Cases

- **XS/S sizing:** Skip Phase 06.5 entirely. No `execution-plan.md`. Main agent proceeds to Execution Loop after A→B Gate.
- **Round N+1:** Phase 06.5 runs again. Create new `execution-plan.md` under `generated/rounds/round-(N+1)/`. Read `issues.md` and the previous round's plan for context.

---

## Part 4: Phase 07 — Execution

### 4.1 Phase B Execution Discipline

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

9. **Scan local environment for tools, skills, and methods** — check available skills, MCP tools, and agent types from session context. Apply relevant [methods](../methods/) via Method Selection at Phase 07 entry.

#### Execution Loop Reminder

Before starting the loop, the agent has:
- [x] Passed the A→B Gate (docs confirmed, branch created)
- [x] Created and confirmed `execution-plan.md`
- [x] Read this file's full content including Phase B Execution Discipline
- [x] Read spec-coding-skill SKILL.md

---

### 4.2 Execution Loop

> ## STOP — Before You Write Any Code
>
> For **every task**, complete these checks before writing a single line:
>
> | # | Check | Skip Consequence |
> |---|-------|------------------|
> | 1 | Read `plan.md` for this task's approach | Wrong design |
> | 2 | Read `init.md § Constitution` | Violate OOP/SOLID |
> | 3 | Read affected source files (in sections if large) | Reimplement or break callers |
> | 4 | Evaluate [Vertical Slice TDD](../methods/01-vertical-slice-tdd.md) trigger | Miss TDD when applicable |
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

### 4.3 Deviation Protocol

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
5. **Wait for decision** — user picks one; if no response after 5 min, execute recommended option as default
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

---

### 4.4 tasks.md Update Rules

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

### 4.5 Requirement Complete — Round End

When all tasks reach `done` (or runnable tasks are `blocked`):

1. **Finalize round issues** — update `generated/rounds/round-NNN/issues.md`: set each entry to resolved / open / wontfix. Open entries remain in `issues.md` for cross-round tracking.

2. **Check `issues.md`** — read all open issues and summarize for the user

3. **Write Round Summary** — update `start-and-resume.md § Round History`:
   ```
   ### Round [N] (complete)
   - **Status:** ✅ done (or ⏸ blocked)
   - **Tasks:** X planned, Y completed, Z deferred
   - **New issues:** ISS-NNN, ISS-MMM
   - **Summary:** What this round achieved.
   ```

4. **Update `.dev/blueprint.md`** — set Round, Phase, Status. See [../shared/05-blueprint-management.md](../shared/05-blueprint-management.md).

5. **Method Selection — Dual-Axis Review:** Significant round with substantial new code?
   - **Yes**: Apply [Dual-Axis Review](../methods/02-dual-axis-review.md). Two parallel reviews (standards + spec). Both must pass.
   - **No**: Record justification. Step 11 self-check checklist suffices.

6. **If no open issues:** declare complete, create PR/merge (step 8):
   > ✅ All tasks complete for [NNN]-[req-name]. Summary: X tasks, Y deviations. No open issues.

7. **If open issues remain:** notify user:
   > ✅ Round N complete. X/Y tasks done. Open: ISS-NNN, ISS-MMM.
   > Start Round N+1? I'll read issues.md, update plan.md and tasks.md incrementally.
   > Or reply **no** to finish.

   If user confirms Round N+1, proceed to Phase 01* (see [01-round-mechanism.md](01-round-mechanism.md) § Phase 01*).

8. **Create a pull request or local merge** using the format in [../shared/03-git-workflow.md](../shared/03-git-workflow.md). For PRs: `gh pr create --title "..." --body "..."`. For local merge: `git checkout main && git merge --no-ff ...`.

---

## Part 5: Appendix — Supporting Rules

### Breaking Changes Policy

Read `project_stage` from `init.md`:
- **`pre-launch` + new module**: breaking changes allowed. Prioritize clean structure over compatibility.
- **`live`** or **modifying existing module**: breaking changes **not allowed**. Smallest change possible. Ask before structural refactor.

### Reading Before Writing

Before modifying any existing file:
- Read the file (in sections if large — never load entire file)
- Identify reusable functions — do not reimplement
- Understand the call graph
- Make the smallest change that satisfies the requirement

### Handling Blockers

When a task cannot proceed:
1. Record in tasks.md Notes: what was attempted, what failed, what is needed
2. Set status to `blocked`
3. Ask the user for guidance

### Git Workflow

See [../shared/03-git-workflow.md](../shared/03-git-workflow.md) for full rules. This section only summarizes execution-loop-specific reminders.

In the Execution Loop — step 11 commits with:
```
git commit -m "[NNN] T-XXX <type>: <imperative summary ≤ 72 chars>"
```

At Requirement Complete — step 8 creates a PR or local merge using the format in ../shared/03-git-workflow.md.

### File Reading and Writing Discipline

- Read files in sections if large — never load an entire large file at once
- Write one file at a time; do not exceed ~200 lines in a single write
- Do not rewrite an entire file when only a small change is needed — use targeted edits
