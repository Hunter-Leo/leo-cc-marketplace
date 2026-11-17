---
name: spec-coding-team-skill
description: "This skill should be used when the user asks to run a multi-agent, PM-led spec-driven development flow for an M-level or larger requirement: forming a team, splitting work units, coordinating executors and reviewers, or adding an optional scientific-fact audit lane. It covers Phase A requirements construction, a hard user gate, team formation, collaborative execution with serialized writes, round review, and integration verification. Do not use for XS/S tasks; use the single-agent spec-coding-skill instead. Triggers: team development, multi-agent, team-mode spec, M-level or larger requirement, agent teams, PM-led, scientific fact audit."
---

# Startup order (STOP)

1. Read `references/essence.md`: the six invariants are the single source of truth; when conflicts arise, they take precedence.
2. Read `references/rails.md`: R-1–R-11 apply to all members; role files only reference the numbers.
3. Detect Agent Teams: `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` and the current session is interactive terminal Claude Code. If not satisfied → present options A/B/C per `references/degradation.md`; silently switching to subagents is forbidden.
4. Run the N0 precheck gate: read `phases/00-precheck.md`. If rated XS/S → stop this skill and switch to `spec-coding-skill`.
5. After N0 passes, create the working directory, write `init.md`, run `bash "${CLAUDE_PLUGIN_ROOT}/scripts/flow.sh" init --run <run>`; only then enter N1.

**STOP semantics**: if any of the 5 steps above is incomplete, creating a git branch, spawning any teammate, and writing business code are all forbidden.

# Orchestration iron rules (violating any one fails the process)

1. **PM must never do the work itself.**
   PM does not write business code, does not write `science-audit.md`, does not modify tests on behalf of the executor, does not issue verdicts on behalf of the reviewer.
   ❌ Counterexample: executor is stuck, so PM directly edits `src/auth.ts` and declares the unit complete.
2. **Never skip phases.**
   N0→N6 must proceed in order; the user gates at N2/N3 cannot be bypassed; when `science_gate.auditor=true`, science-auditor is mandatory.
   ❌ Counterexample: user says "just start writing", PM skips N2 and creates the branch directly.
3. **Never withhold information.**
   Upstream artifacts must be written to disk; they must not exist only in the PM's context or the spawn prompt.
   ❌ Counterexample: PM writes "the research conclusion is X" in the spawn prompt, but there is no `research.md` on disk.
4. **Never terminate early.**
   While waiting for a teammate, do not analyze on your own, do not draw conclusions for it, do not act first and report later.
   ❌ Counterexample: reviewer has not reported back, PM looks at the diff, thinks it is fine, and advances the unit to `approved`.
5. **Never self-declare completion.**
   A unit must pass through `approved` → `merged` → `verified` in order, and `check-team-complete.sh` must output `OK`.
   ❌ Counterexample: declaring complete as soon as `git commit` succeeds, with no test output.
6. **Never run the same role in parallel / never allow two writers at once.**
   Implementation units are always serialized (single global claim); `owned_files` being pairwise disjoint is only a precondition for scheduling, not permission to write in parallel. At any time there can be only one instance of a given role.
   ❌ Counterexample: two executors modify `src/router.ts` at the same time, on the grounds that "they are doing different features".
7. **Never degrade silently.**
   Any degradation must be written to `decisions.md` and explicitly `confirmed` by the user. Degradation includes: cutting roles, disabling the science channel, removing read-only overlap, downgrading major to minor, falling back from team to single agent/subagent.
   ❌ Counterexample: running low on tokens, PM quietly stops spawning science-auditor.

# Phase overview and mission mapping

```
N0 Precheck ──XS/S or not triggered──> spec-coding-skill (single-agent mode)
   │ M/L and triggers hold
   ▼
N1 Phase A (PM writes init/plan/tasks/decisions; up to 3 concurrent read-only roles: explorer, architect, researcher)
   ▼
N2 Hard Gate (explicit user `confirmed`) ──rejected/changes requested──> stay at gate to revise
                                                                (to revise in N1: `transition --to blocked`, then `bash "${CLAUDE_PLUGIN_ROOT}/scripts/flow.sh" recover`)
   ▼
N3 Formation (split units by owned_files → team-plan → user `confirmed`)
   ▼
N4 Execution (claim/in_progress; executor implements; checkpoint every 3 units)
   ▼
N5 Round Review (reviewer; mandatory when auditor is enabled)
   ├── unresolved items ──> same-session Round N+1 (mission remains reviewing)
   └── no unresolved items
   ▼
N6 Verification (approved → merged → verified)
```

| Phase | `flow.json.mission` | Entry condition |
|---|---|---|
| N0–N1 | `planning` | `bash "${CLAUDE_PLUGIN_ROOT}/scripts/flow.sh" init` complete |
| N2–N3 | `gate` | `bash "${CLAUDE_PLUGIN_ROOT}/scripts/flow.sh" transition --to gate` when submitting the N2 template to the user |
| N4 | `executing` | after user confirmation at N3, `bash "${CLAUDE_PLUGIN_ROOT}/scripts/flow.sh" transition --to executing` |
| N5–N6 | `reviewing` | after all implementation units are `for_review`/`approved`, `bash "${CLAUDE_PLUGIN_ROOT}/scripts/flow.sh" transition --to reviewing` |
| End | `verified` | all implementation units `verified` and completion check `OK` |

`blocked` is the human-adjudication terminal state, enterable only by PM when a stop condition is hit.

# Role quick-reference table

PM is the main session; it does not spawn and is not counted as a role. Role files live at the plugin root: `${CLAUDE_PLUGIN_ROOT}/agents/spec-<role>.md`.

| Role | archetype | Lifecycle | Exclusive artifacts | Write permission |
|---|---|---|---|---|
| explorer | Makes-sense (Explainer) | one-shot in N1; may supplement once in N3 | `inspect.md` | read-only code |
| architect | Patterned (Contract Designer) | one-shot in N1; may supplement once in N3 | `architecture-review.md` | read-only code |
| science-researcher | Sourced (Researcher) | when `science_gate.researcher=true` | `research.md`, `fixtures/` | research artifacts only |
| executor | Runnable (Builder) | N4–N6, may span rounds | code and tests within `owned_files` | only within claim scope |
| reviewer | Refutable (Reviewer) | from the first N4 checkpoint through N6 | its own section in `findings.md` | read-only code, no edits |
| science-auditor | Usable (Verifier) | when `science_gate.auditor=true` | `science-audit.md` | read-only, no code or research edits |

Teammates do not inherit PM conversation history; the primer and unit block must be written into the spawn prompt, see `phases/04-execution.md`.

# File ownership table

`<run>` is the single term for the run identifier throughout: it equals the `.dev/<NNN>-<req>` directory name assigned by N0. Requirement docs live in `.dev/<run>/generated/`; runtime state lives in `.team/<run>/`.

| Path | Sole writer | Other roles |
|---|---|---|
| `generated/init.md` | PM | read-only |
| `generated/plan.md` | PM | read-only |
| `generated/tasks.md` | PM | read-only |
| `generated/decisions.md` | PM (append-only) | read-only |
| `generated/team-plan.md` | PM | read-only |
| `generated/primer.md` | PM | read-only (content injected into spawn prompt) |
| `generated/findings.md` | each role writes only its own section; PM writes the summary/adjudication section | read-only within a section |
| `generated/progress.md` | all members append only | append only |
| `generated/dead-ends.md` | PM (append-only) | read-only |
| `generated/handoff.md` | PM | read-only |
| `generated/inspect.md` | explorer | read-only |
| `generated/architecture-review.md` | architect | read-only |
| `generated/research.md` | science-researcher | read-only |
| `generated/fixtures/` | science-researcher; frozen after delivery | read-only |
| `generated/science-audit.md` | science-auditor | read-only |
| `.team/<run>/flow.json` | PM initializes/maintains; modified by the flow script during execution | read-only |
| `.team/<run>/prompts/<unit>.md` | PM | read-only |
| `.team/<run>/verdicts/` | teammate report-back written to disk (required while a claim is active) | read-only |
| source code/tests declared in `owned_files` | executor | read-only |

While a claim exists during execution, writes not covered by an exception must fall within `claim.files`; when there is no claim in N1 the hook allows the write, but role lane constraints still apply.

# State machine and flow script

Runtime state: `.team/<run>/flow.json`.

```json
{
  "run": "001-example",
  "round": 1,
  "mission": "planning",
  "science_gate": {"researcher": false, "auditor": false},
  "branch": "feat/001-example",
  "units": [
    {"id": "U-01", "owner": "spec-executor", "owned_files": ["src/a.ts", "tests/a.test.ts"],
     "lane": "pending", "failures": 0}
  ],
  "claim": null,
  "counters": {"consecutive_same_error": 0},
  "events": []
}
```

mission states: `planning → gate → executing → reviewing → verified`; `blocked` is the human-adjudication terminal state.
Unit states: `pending → in_progress → for_review → approved → merged → verified`, with side paths `changes_requested`, `blocked`.

| Command | Purpose |
|---|---|
| `bash "${CLAUDE_PLUGIN_ROOT}/scripts/flow.sh" init --run <run>` | creates `flow.json`, `mission=planning`, `branch=feat/<run>` |
| `bash "${CLAUDE_PLUGIN_ROOT}/scripts/flow.sh" add-unit --id <U-ID> --owner <role> --files "<glob,glob>"` | registers one implementation unit in N3 |
| `bash "${CLAUDE_PLUGIN_ROOT}/scripts/flow.sh" set --science-gate-researcher <true\|false> --science-gate-auditor <true\|false> [--branch <b>] [--round <n>]` | sets the science gate, branch, or round |
| `bash "${CLAUDE_PLUGIN_ROOT}/scripts/flow.sh" next` | outputs the next suggested action (`KEY action=...`) |
| `bash "${CLAUDE_PLUGIN_ROOT}/scripts/flow.sh" transition --to <mission> [--by <name>]` | advances mission |
| `bash "${CLAUDE_PLUGIN_ROOT}/scripts/flow.sh" transition --unit <U-ID> --to <unit-state> [--by <name>]` | advances a unit |
| `bash "${CLAUDE_PLUGIN_ROOT}/scripts/flow.sh" claim --unit <U-ID> [--files "<glob,glob>"] [--by <role>]` | acquires the write lock; when `--files` is omitted it defaults to the unit's `owned_files`, and when given explicitly must be a subset of them |
| `bash "${CLAUDE_PLUGIN_ROOT}/scripts/flow.sh" release` | releases only the write lock (does not change unit state) |
| `bash "${CLAUDE_PLUGIN_ROOT}/scripts/flow.sh" reopen --unit <U-ID> --reason "<text>" [--force true]` | any unit state → `pending`; when `failures >= 3`, requires user adjudication and then `--force true` |
| `bash "${CLAUDE_PLUGIN_ROOT}/scripts/flow.sh" recover` | releases a stale claim; `mission=blocked` → `planning`/`executing` |
| `bash "${CLAUDE_PLUGIN_ROOT}/scripts/flow.sh" status` | outputs mission/round/units/claim/blockers/next |
| `bash "${CLAUDE_PLUGIN_ROOT}/scripts/flow.sh" checkpoint --note "<text>"` | writes a snapshot to `.team/<run>/snapshots/` |
| `bash "${CLAUDE_PLUGIN_ROOT}/scripts/check-lanes.sh" [--json]` | validates that `owned_files` are pairwise disjoint (exit 1 = definite overlap, N3 gate) |

Key constraints:

- The flow script only validates whether state transitions are legal, not content quality; content gates are handled by each phase's checklist and `check-team-complete.sh`.
- Only one global `claim` exists at a time; writes are serialized. Read-only roles may read in parallel, but writing artifacts requires holding a claim or hitting an exception path.
- `release` only clears the lock and does not advance state; state advancement must use `transition --unit`.
- `changes_requested` causes `failures += 1`; when `failures >= 3`, `changes_requested → in_progress` is rejected by the script, and a new unit must be split off or the user must adjudicate. `reopen` must not be used to bypass this limit.
- PM registers implementation units one by one with `add-unit` in N3, then must run `bash "${CLAUDE_PLUGIN_ROOT}/scripts/check-lanes.sh"`; on exit code 1, go back and re-split. Reviewer / auditor verification arrangements are not registered.

N0–N6 advancement preconditions (content gates; the flow script only handles state order):

| Advancement | Must hold |
|---|---|
| N0→N1 | `init.md § N0 Precheck Determination` complete; `flow.json` exists and `mission=planning` |
| N1→N2 | `plan.md`, `tasks.md`, `decisions.md` exist; after submitting the template, `transition --to gate` |
| N2→N3 | `decisions.md` contains the user's original `confirmed` text; git branch created; `primer.md` written |
| N3→N4 | `team-plan.md` has the user's `confirmed`; `flow.json.units` non-empty; `transition --to executing` |
| N4→N5 | all implementation units are `for_review`, `approved`, `merged`, or `verified`; no claim; `transition --to reviewing` |
| N5→N6 | `findings.md` has no unresolved blocker/critical/unaccepted major; when the auditor is enabled, `science-audit.md` has no `FAIL`; an `UNVERIFIABLE` verdict never permits `verified` — only explicit user adjudication recorded in `decisions.md` can close it, and the audit file must then carry a `PASS` or a decision reference |
| N6→verified | all implementation units `verified`; after `transition --to verified`, only when `check-team-complete.sh` outputs `OK` may completion be reported |

# Severity and report-back contract

| Level | Definition | Gate behavior |
|---|---|---|
| blocker | correctness/security/data loss/contract break | stop immediately; do not continue the current unit |
| critical | violates invariants or acceptance criteria | merged is forbidden |
| major | spec deviation with functional impact | blocking by default; released only after the user accepts it as debt (`findings.md` status changed to `accepted` + ADR recorded in `decisions.md`) |
| minor | style/naming/missing docs | non-blocking, must be recorded |
| nit | optional improvement | may or may not be recorded |

Advancement formula: `blocker == 0 && critical == 0 && unaccepted_major == 0`.
severity is assigned by reviewer / science-auditor; authors may only dispute; downgrading must be written to `decisions.md`.

Every teammate must report back per `rails.md` R-10 when it finishes; while a claim is active, a missing `verdict` will be rejected by the SubagentStop hook, and PM must not advance.

# Scale and cost

- Default 2–3 teammates; cap 4 (including reviewer; science-auditor counts toward the cap).
- Team token consumption is 3–10× that of a single agent. Before forming a team you must be able to answer: which dimension the single agent lacks, what happens if each role is removed, who is the bottleneck.
- If any of these cannot be answered → fall back to `spec-coding-skill` and record the reason in `decisions.md`.

# Templates

Copy from `${CLAUDE_PLUGIN_ROOT}/skills/spec-coding-team-skill/templates/`; do not invent ad-hoc formats.

| Template | Filled by |
|---|---|
| `templates/team-plan.md` | PM in N3 |
| `templates/findings.md` | reviewer / science-auditor / PM (each own section) |
| `templates/decisions.md` | PM (D-`<NNN>`, ADR-`<NNN>`, science_gate changes) |
| `templates/progress.md` | all members (append-only) |
| `templates/dead-ends.md` | PM (append-only) |
| `templates/handoff.md` | PM before interruption or round end |
| `templates/research.md` | science-researcher |
| `templates/science-audit.md` | science-auditor |

# Reading order

Paths within this skill are relative to the skill directory (`${CLAUDE_PLUGIN_ROOT}/skills/spec-coding-team-skill/`); role files are at the plugin root `${CLAUDE_PLUGIN_ROOT}/agents/`.

1. `references/essence.md`
2. `references/rails.md`
3. Read `phases/00-precheck.md` → `01` → `02` → `03` → `04` → `05` → `06` by phase
4. The current role reads `${CLAUDE_PLUGIN_ROOT}/agents/spec-<role>.md`
5. As needed, read `references/science-gate.md` / `degradation.md` / `team-invariants.md`
