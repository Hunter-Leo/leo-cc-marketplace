# spec-coding-team-skill

> **Status: experimental.** Depends on Claude Code's experimental Agent Teams capability; interfaces and behavior may change between versions.
>
> In one sentence: hand M-level and larger coding requirements to a PM-led multi-agent team, using files and a state machine to guarantee that "plan → user confirmation → collaborative execution → independent review → integration acceptance" relies on neither memory nor good intentions.

## 1. What problem does it solve

When a single context cannot hold a large requirement, the model silently drops constraints, treats "finished writing" as "verified", and treats plan deviation as efficiency optimization. This skill turns those three failure modes into an inspectable process using **persisted artifacts + mechanical gates + independent verification contexts**.

## 2. Division of labor with the single-agent version

| Requirement size | Criterion (if any applies, take the highest tier) | Use |
|------------------|--------------------------------------------------|-----|
| XS | ≤1 file, ≤30 lines, a single behavior | `spec-coding-skill` single-agent |
| S | 2–5 files or ≤150 lines, does not cross module interfaces | `spec-coding-skill` single-agent |
| M | 6–20 files or 151–800 lines or spans 2–3 modules | this skill (team edition) |
| L | >20 files or >800 lines or spans ≥4 modules/repositories | this skill (team edition, N3 may split into waves) |

The team edition additionally requires `T1 && (T2 || T3 || T4)`: size reaches M/L, and there is parallel benefit, an independent-verification need, or the user explicitly asks for a team. When the size is insufficient or the triggers do not hold, it **explicitly falls back** to single-agent mode and will not force a team.

The cost of teaming is that multi-agent consumes **3–10× more tokens** than single-agent; the default team size is 2–3 people, with a maximum of 4.

## 3. Installation and enabling

```bash
/plugin marketplace add Hunter-Leo/leo-cc-marketplace
/plugin install leo-team-plugin@leo-cc-marketplace
```

Agent Teams must be explicitly enabled. Add the following to `~/.claude/settings.json` or the project's `.claude/settings.json`:

```json
{
  "env": {
    "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1"
  }
}
```

You can also `export CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` in the current shell. After setting it, you must **restart the Claude Code session**.

Limitation: it works only in **interactive terminal Claude Code**. `claude -p` and the Agent SDK will not spawn teammates even if the variable is 1.

Verification:

```bash
[ "${CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS:-0}" = "1" ] && echo teams || echo subagent
```

## 4. Six roles

The PM is the main session and is not counted among the roles; the other six are spawned by the PM.

| Role | agent file | Lifecycle | Exclusive artifacts | Write permission |
|------|-----------|-----------|---------------------|------------------|
| explorer | `agents/spec-explorer.md` | N1, one-shot | `inspect.md` | read-only on code |
| architect | `agents/spec-architect.md` | N1, one-shot | `architecture-review.md` | read-only on code |
| science-researcher | `agents/spec-science-researcher.md` | N1; when science gate is on | `research.md`, `fixtures/` | write research artifacts only |
| executor | `agents/spec-executor.md` | N4–N6, may span rounds | code and tests within `owned_files` | own lane only |
| reviewer | `agents/spec-reviewer.md` | from N4's first checkpoint to N6 | its own section in `findings.md` | read-only on code, no edits |
| science-auditor | `agents/spec-science-auditor.md` | every round at N5; mandatory when auditor is enabled | `science-audit.md` | read-only, no edits to code or research |

Roles write only the paths declared in their own `Lane`; out-of-bounds writes are rejected by the `PreToolUse` hook. Every role must return a `verdict` per rails R-10; a missing verdict counts as incomplete.

## 5. A typical run

| Phase | What to do | Key gate |
|-------|-----------|----------|
| **N0 Precheck** | Task Sizing, four trigger-condition checks, science gate inquiry, write `init.md` | if not sized M/L → fall back to single-agent |
| **N1 Phase A** | PM writes `init.md` / `plan.md` / `tasks.md` / `decisions.md`; runs explorer / architect / researcher in parallel as needed | upstream artifacts must be persisted |
| **N2 Hard Gate** | PM personally submits the plan, branch name, and acceptance criteria to the user | no branch may be created before the user explicitly confirms |
| **N3 Formation** | Split work units by `owned_files`, write `team-plan.md` and startup prompts, decide scheduling | the user confirms again; overlapping write sets must be merged or serialized |
| **N4 Execution** | Claim units, executor implements and self-tests, one checkpoint every 3 units | cannot enter review until a unit is complete |
| **N5 Round Review** | Reviewer dual-axis review; auditor reviews mandatorily when the gate is on | if anything is unresolved → enter Round N+1 in the same session |
| **N6 Verification** | Obtain `approved` → `merged` → `verified` evidence in order | `check-team-complete.sh` outputs `OK` |

Start command:

```bash
/spec-team <requirement description or .dev/<NNN>-<req>/ path>
```

View progress:

```bash
/team-status [run name or .dev requirement directory]
```

Archive a finished run (archive only, never delete; type `archive` verbatim to confirm before execution):

```bash
/team-reset <run name>
```

## 6. Artifact layout

Requirement documents (committable, auditable):

```text
.dev/
└── 001-auth-refactor/
    └── generated/
        ├── init.md                # PM: N0 decision, goal, non-goals, acceptance criteria, constraints, glossary, risks
        ├── plan.md                # PM: implementation plan
        ├── tasks.md               # PM: task table
        ├── decisions.md           # PM: append-only decisions and user-confirmation records
        ├── team-plan.md           # PM: work units, owned_files, scheduling decision, checkpoints
        ├── primer.md              # PM: minimal context injected at spawn
        ├── findings.md            # independent section per role + PM summary
        ├── progress.md            # append-only action timeline
        ├── dead-ends.md           # attempts that failed and should not be retried
        ├── handoff.md             # recovery entry point after interruption
        ├── inspect.md             # explorer
        ├── architecture-review.md # architect
        ├── research.md            # science-researcher (optional)
        ├── fixtures/              # science-researcher (frozen after delivery)
        └── science-audit.md       # science-auditor (optional)
```

Team run state (mechanical state, usually not committed):

```text
.team/
└── 001-auth-refactor/
    ├── flow.json                  # mission / round / units / claim / events
    ├── snapshots/                 # checkpoint snapshots
    └── verdicts/                  # persisted teammate reply contracts
```

Common state commands:

```bash
bash "${CLAUDE_PLUGIN_ROOT}/scripts/flow.sh" init --run <req-name>
bash "${CLAUDE_PLUGIN_ROOT}/scripts/flow.sh" status
bash "${CLAUDE_PLUGIN_ROOT}/scripts/flow.sh" next
bash "${CLAUDE_PLUGIN_ROOT}/scripts/flow.sh" checkpoint --note "..."
bash "${CLAUDE_PLUGIN_ROOT}/scripts/check-team-complete.sh"
```

## 7. How to enable the science channel

The science channel is **off by default**, to avoid paying extra cost for ordinary engineering requirements. N0 asks once:

| Option | researcher | auditor | Applies to |
|--------|-----------|---------|-----------|
| A (default) | ✗ | ✗ | ordinary engineering requirements |
| B | ✓ | ✗ | only literature research or corpus preparation needed, no independent audit |
| C | ✗ | ✓ | external scientific consensus available for comparison, but no dedicated research needed |
| D | ✓ | ✓ | scientific computing, algorithm implementation, paper reproduction, metric claims |

Typical enabling conditions: implementing a formula or algorithm from a paper/standard, claiming "X% improvement" or "error below Y", depending on a corpus or benchmark data, or conclusions that affect business decisions.

The choice is recorded in the N0 decision in `init.md` and the science gate table in `team-plan.md`; the `science_gate` field in `.team/<run>/flow.json` is read by hooks and the completion check. Once enabled:

- Every research conclusion must include a source and confidence level (`established` / `contested` / `assumption`); fabricating literature is forbidden.
- `fixtures/` is frozen after delivery and read-only in Phase B.
- Any failure of the auditor's five checks yields `FAIL` and enters Round N+1; an unexplained `UNVERIFIABLE` counts as `FAIL`.
- The completion criterion is upgraded from "no unresolved items in `findings.md`" to "no unresolved items and `science-audit.md` exists with no FAIL".

## 8. Known limitations

- **Experimental capability**: depends on `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS`; behavior may change with Claude Code versions.
- **No session resumption**: teammate context is lost after the session ends; recovery can only rely on `handoff.md` and `dead-ends.md` and re-spawn.
- **Teammates cannot spawn further**: nested teams are not supported; the PM is the only scheduler.
- **No worktree isolation**: all agents share the same working tree; write operations are serialized by the global `claim`, read-only analysis and write operations may overlap, and read-only roles may also read in parallel. Pairwise disjointness of `owned_files` is a necessary condition for scheduling, not permission for parallel writes.
- **Interactive sessions only**: `claude -p` and the Agent SDK do not support teammate spawn.
- **High cost**: 3–10× tokens; fall back to single-agent mode when the size is insufficient or the triggers do not hold.

## 9. FAQ

**Q: Why was my write rejected?**

Writes are governed by two rules: `claim.files` in `flow.json` and the `owned_files` the PM gave you in `team-plan.md` (`claim.files` defaults to `owned_files`, but may also be a subset of it). Only matching paths may be written; `findings.md`, `progress.md`, `inspect.md`, `architecture-review.md`, `research.md`, and `science-audit.md` are special exemptions. First run `flow.sh status` to see the current claim, then check the allowed scope; do not retry the same out-of-bounds path—record it in `findings.md` and report to the PM.

Note: `Write`/`Edit` interception is exact; `Bash` only blocks common write forms (redirection, `tee`, `cp`/`mv`/`ln`/`rm`, `sed -i`, `dd of=`, `truncate`, etc.) and is **not a sandbox**. Inline scripts such as `python -c` / `node -e` cannot be statically validated and are treated as out-of-bounds; use `Write`/`Edit` when you need to write files.

**Q: Why did it not enter the team flow?**

N0 sized the task as XS/S, or `T1 && (T2 || T3 || T4)` does not hold. The flow explicitly explains the reason and recommends single-agent mode; if the user insists on a team, the PM writes the override decision into `decisions.md` and executes with a minimal 2-person team (executor + reviewer).

**Q: Can people be added or the scheduling arrangement changed mid-run?**

Yes, but only the PM may rewrite `team-plan.md` and obtain user confirmation; teammates must not expand their own authority. New units are still judged by pairwise disjoint `owned_files`.

**Q: What is the difference between `approved`, `merged`, and `verified`?**

`approved` means the review passed, `merged` means it has entered the integration branch, and `verified` means acceptance evidence is complete. The three are not interchangeable; completion must not be announced if any is missing.

**Q: How do I continue after an interruption?**

First run `/team-status` to see the on-disk state, then read the `resumption_prompt` in `handoff.md`; do not assume old teammates are still alive—you must re-spawn and obtain an acknowledgment from this session.

**Q: Can the science channel be turned off?**

Yes; choose A at N0 (off by default). Turning it off or downgrading it mid-run must be written into `decisions.md` and explicitly confirmed by the user; silent disabling counts as a flow failure.

**Q: Does `/team-reset` delete data?**

No. It only moves `.team/<run>/` to `.team/archive/<run>-<UTC timestamp>/`; it deletes no files and does not modify requirement artifacts under `.dev/<run>/`. Before archiving it shows a summary and requires typing `archive` verbatim to confirm; runs with `mission=executing` or a non-empty `claim` are refused. To restore, move the archive directory back to `.team/<run>/`.
