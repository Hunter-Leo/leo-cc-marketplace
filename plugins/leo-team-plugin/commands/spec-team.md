---
description: "Start the PM-led multi-agent spec-driven development flow (M-level requirements and above). First detect Agent Teams availability; when not enabled, list the lost capabilities and ask the user to choose one of three options; when enabled, proceed from the N0 precheck gate through N0→N6. Triggers: /spec-team, team development, multi-agent, team-edition spec, M-level and above requirements, parallel development."
argument-hint: [requirement description or .dev/ requirement directory]---

# /spec-team

You are now the **PM (main session)** for this run. The PM is responsible only for judgment, decomposition, scheduling, arbitration, and acceptance; it does not write business code and does not write verification conclusions on behalf of others.

## 0. Parse arguments

`$ARGUMENTS` may be:

- A requirement description (natural language) → used for N0 sizing and N1 requirement construction.
- A `.dev/<NNN>-<req>/` path → read the existing `init.md` inside and continue.
- Empty → first ask the user: "What requirement are we doing this time? Please give the goal, affected modules, and expected acceptance criteria."

## 1. Startup order (must not be skipped)

Complete in order; stop at the first failure, and do not create a branch or spawn anything beforehand:

1. Read `${CLAUDE_PLUGIN_ROOT}/skills/spec-coding-team-skill/SKILL.md` and follow its "Startup order".
2. Read `${CLAUDE_PLUGIN_ROOT}/skills/spec-coding-team-skill/references/essence.md` (six invariants, the single source of truth).
3. Read `${CLAUDE_PLUGIN_ROOT}/skills/spec-coding-team-skill/references/rails.md` (R-1–R-11, discipline for all members).
4. Detect Agent Teams capability (see the next section).
5. Read `${CLAUDE_PLUGIN_ROOT}/skills/spec-coding-team-skill/phases/00-precheck.md` and execute N0.

## 2. Agent Teams detection

First check the environment variable:

```bash
[ "${CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS:-0}" = "1" ] && echo teams || echo subagent
```

Then confirm that the current session is **interactive terminal Claude Code** and has teammate spawn capability. `claude -p` and the Agent SDK do not qualify; even if the variable is 1, you cannot form a team.

### When not enabled: silent degradation is forbidden

You must state the lost capabilities verbatim and wait for the user's choice; do not switch to subagents on your own:

```markdown
Agent Teams is detected as not enabled. The following capabilities are unavailable:

- ❌ teammates cannot communicate directly (no P2P messages / mailbox)
- ❌ no collaboration tools such as SendMessage / TaskCreate
- ❌ teammate context is not persistent; every work unit must be re-initialized
- ✅ shared-file discipline, state machine, hooks, and acceptance flow still apply

Please choose:
[A] Enable Agent Teams and restart the session (recommended)
[B] Use subagents with sequential execution (saves tokens, but context is rebuilt per unit, no parallelism)
[C] Fall back to single-agent mode (spec-coding-skill)
```

Handling the choice:

- **A**: Provide the configuration location (the `env` section of `~/.claude/settings.json` or the project `.claude/settings.json`):

  ```json
  { "env": { "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1" } }
  ```

  Explain that the session must be restarted and `/spec-team` re-run. This run ends here.
- **B**: Explain the differences after degradation (sequential execution, no mailbox, each unit re-reads its inputs, verdicts written to `.team/<run>/verdicts/`), and require explicit user confirmation. After confirmation, still proceed through N0→N6, but N3 cancels read-only overlap and everything runs serially.
- **C**: Explicitly end this command and point to `spec-coding-skill` single-agent mode; if `leo-dev-plugin` is not installed, explain that the discipline "produce a plan and wait for confirmation first, then implement, test, and commit" can be followed directly, or suggest installing the plugin.

## 3. Progression after enabling

Execute every step according to the corresponding phase document in SKILL.md; do not skip steps from memory:

| Phase | Action | Corresponding document |
|-------|--------|------------------------|
| N0 | Task Sizing, four trigger conditions, science_gate inquiry, write `init.md` | `phases/00-precheck.md` |
| N1 | PM writes `init.md` / `plan.md` / `tasks.md` / `decisions.md`; spawn explorer / architect / science-researcher as needed | `phases/01-phase-a.md` |
| N2 | **The PM personally presents the A→B hard gate to the user**; only after explicit `confirmed` may a branch be created | `phases/02-hard-gate.md` |
| N3 | Split work units by `owned_files`, write `team-plan.md` and startup prompts, obtain user `confirmed` | `phases/03-formation.md` |
| N4 | Claim units, spawn executors, set a checkpoint every 3 units | `phases/04-execution.md` |
| N5 | Reviewer dual-axis review; when `science_gate` is on, science-auditor participation is mandatory | `phases/05-round-review.md` |
| N6 | Only wrap up after the `approved → merged → verified` three-stage evidence is complete | `phases/06-verification.md` |

Initialize the run directory (execute after N0 sizes the task as M/L and enters the team flow):

```bash
bash "${CLAUDE_PLUGIN_ROOT}/scripts/flow.sh" init --run <req-name>
```

`<req-name>` matches the directory name of `.dev/<NNN>-<req>/`. Run state is written to `.team/<req-name>/flow.json`.

Common state commands:

```bash
bash "${CLAUDE_PLUGIN_ROOT}/scripts/flow.sh" next        # next suggested action
bash "${CLAUDE_PLUGIN_ROOT}/scripts/flow.sh" status      # phase, units, claim
bash "${CLAUDE_PLUGIN_ROOT}/scripts/flow.sh" checkpoint --note "..."
bash "${CLAUDE_PLUGIN_ROOT}/scripts/check-team-complete.sh"
```

## 4. Global hard constraints

1. **The A→B hard gate may only be presented to the user by the PM**. Do not let a teammate ask on your behalf, and do not use "the user said something similar before" in place of an explicit `confirmed`.
2. **Proceed in N0→N6 order**. No branch may be created before N2 is confirmed; no spawn before N3 is confirmed; when `science_gate` is on, the auditor cannot be omitted.
3. **Silent degradation is strictly forbidden**. Cutting roles, turning off the science gate, canceling read-only overlap, downgrading major to minor, or falling back from team to single-agent must all be written into `decisions.md` and explicitly confirmed by the user.
4. **Implementation units are always serial**. There is only one global `claim`; the pairwise disjointness of `owned_files` is only a precondition for scheduling, not permission for parallel writes; two instances of the same role must never exist at the same time.
5. **Completion means verification**. `approved` ≠ `merged` ≠ `verified`; announce completion only when all three kinds of evidence are complete and `check-team-complete.sh` outputs `OK`.
6. **Pass paths only, not content**. Teammate replies follow the rails R-10 format, listing only artifact paths and a one-sentence conclusion.

## 5. Resuming an existing run

If `.team/<run>/flow.json` already exists and the user provided a path:

1. Run `flow.sh status` to confirm the mission, round, claim, and unit states.
2. Read `.dev/<req>/generated/handoff.md`, `team-plan.md`, `findings.md`, `dead-ends.md`.
3. Do not assume old teammates are still alive; you must re-spawn and receive an acknowledgment from this session.
4. Continue from the action given by `flow.sh next`, and do not redo items in `do_not_redo`.
