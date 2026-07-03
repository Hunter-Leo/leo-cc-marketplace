# Start and Resume Guide — [NNN]-[req-name]
**Current Round:** 1

## Quick Start
1. Read `.dev/blueprint.md` — project-wide status across all requirements
2. Read `init.md` — this requirement's scope
3. Read `generated/rounds/round-[NNN]/plan.md` — technical approach (NNN = current round from above)
4. Read `generated/rounds/round-[NNN]/tasks.md` — find the next `not-started` task
5. Review the standards sections below before writing any code

## Resuming After Interruption
1. Read `00-agent-execution.md § Handling Project Overview Queries` for the status display format
2. Read `.dev/blueprint.md` — see all requirements, phases, and overall project status
3. Check `issues.md` for open issues from previous rounds
4. Open `generated/rounds/round-[NNN]/tasks.md` and find the first task not in `done`
5. If a task is `in-progress`, read its Notes for context before continuing
6. If a task is `blocked`, read the Notes and address the blocker first
7. Review the standards sections below before continuing

## Session Bootstrap
When entering an existing project with `.dev/` content, bootstrap the session before any work:

1. Check `.dev/blueprint.md` — if missing, scan `.dev/` directories to reconstruct from existing `init.md` files
2. Read the blueprint and for each active or blocked requirement, read `tasks.md`
3. Present the full status to the user proactively
4. Ask the user which requirement to focus on, or proceed with the active one
5. Open `issues.md` for open issues (if round > 1)
6. Open `generated/rounds/round-[NNN]/tasks.md` for the chosen requirement

## Key Documents
- Requirement: `.dev/[NNN]-[req-name]/init.md`
- Issues (cross-round): `.dev/[NNN]-[req-name]/issues.md`
- Current plan: `.dev/[NNN]-[req-name]/generated/rounds/round-[NNN]/plan.md`
- Current tasks: `.dev/[NNN]-[req-name]/generated/rounds/round-[NNN]/tasks.md`

## Round History
**Current Round:** [N]

### Round [N] (complete)
- **Status:** [completed / blocked]
- **Location:** `generated/rounds/round-NNN/`
- **Tasks:** X planned, Y completed, Z deferred
- **New issues:** ISS-NNN, ISS-MMM
- **Open issues:** W remaining
- **Summary:** One or two sentences about what this round achieved.

## Constitution
See `init.md § Constitution` for this requirement's design rules. Key principles that apply to every task:
- **OOP & SOLID** — encapsulation, SRP, OCP (no if/elif chains), DIP (depend on abstractions)
- **Type annotations** — all function/method parameters and return types
- **Docstrings** — every public class, function, and file
- **Testing** — normal cases + edge cases + error cases
- **No hardcoded secrets** — use environment variables
- **Import rules** — no lazy imports; restructure to avoid circular deps before using `TYPE_CHECKING`

## Git Workflow
Branch: `<type>/[NNN]-[req-name]`

Commit format:
```
[NNN] T-XXX <type>: <imperative summary ≤ 72 chars>
```

Types: `feat` · `fix` · `refactor` · `test` · `docs` · `style` · `perf` · `ci` · `build` · `chore`

## Phase B Discipline Reminder
Every agent entering Phase B MUST follow these rules:

1. **Read this document** — especially Constitution, Git Workflow, and Phase B Execution Discipline (see `phase-b/00-start-and-resume.md`)
2. **Read spec-coding-skill SKILL.md** — full methodology, state machine, deviation protocol
3. **No implicit fallback** — do not silently catch errors, add hidden retry logic, or log-and-continue past real failures. Always use the Deviation Protocol.
4. **Integration tests: no mocking internal code or external dependencies** — mock only at system boundaries
5. **Follow the execution loop step by step** — never skip steps or batch tasks
6. **Update tasks.md on every status change** — not-started → in-progress → done/blocked, with Notes
