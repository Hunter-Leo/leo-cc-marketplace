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

**Entry (Phase 06):** `tasks.md` exists at `.dev/[NNN]-[req-name]/generated/rounds/round-NNN/tasks.md`.
**Exit (Phase 06):** `start-and-resume.md` created at `.dev/[NNN]-[req-name]/generated/start-and-resume.md`.
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

### Step 2.5 — Return to Planning (if needed after branch creation)

If the user requests changes after branch creation that require significant re-planning:
1. `git checkout -b <type>/[NNN]-[req-name]-rollback-$(date +%s)` — preserve work for reference
2. `git checkout main` — return to main
3. `git branch -D <type>/[NNN]-[req-name]` — delete the branch
4. Update `.dev/blueprint.md`: reset requirement to the relevant earlier phase
5. Re-enter Phase 04 or Phase 02 depending on the scope of changes needed
6. Present to user: "Returned to planning. Branch archived for reference."

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

1. **Execution Agent** (execution-capable model) — executes tasks in sequence, may batch simple tasks
2. **Review Agent** — reviews after each execution agent's batch
3. **Auto-advance** — proceeds without interactive pauses; blockers pause per Deviation Protocol

> **Batching limit:** execution agent runs at most 3 consecutive tasks before a review checkpoint. After 3 tasks: pause for review. Review agent checks code quality, test coverage, and plan adherence. If the task list has fewer than 3 tasks total, this limit does not apply.

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

> After completing Phase 06.5 Execution Planning, enter the [Execution Loop](02-execution-loop.md). That file contains the Phase B Execution Discipline, 12-step Execution Loop, Deviation Protocol, tasks.md update rules, and Requirement Complete checklist.

**Entry (Phase 07):** `start-and-resume.md` + `execution-plan.md` exist.
**Exit (Phase 07):** All tasks reach `done`, `.dev/blueprint.md` updated.

### 4.1 Phase B Execution Discipline and Execution Loop

The complete Phase B Execution Discipline, 12-step Execution Loop, Deviation Protocol, tasks.md Update Rules, and Requirement Complete checklist have been moved to [02-execution-loop.md](02-execution-loop.md).

**Read `02-execution-loop.md` before starting Phase 07.**

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
