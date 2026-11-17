# N0 Precheck — Pre-gate

> Goal: before spending any team cost, determine "should we form a team" and initialize runtime state. This phase does not create a git branch, does not write business code, does not spawn teammates.
> Prerequisite: `references/essence.md`, `references/rails.md` have been read.

## Steps

1. **Assign requirement number**: scan `.dev/` for directories matching `[0-9]{3}-*`, take the max number +1, zero-pad to three digits; create `.dev/` if it does not exist. The chosen directory name is the run identifier used as `<run>` throughout this skill.
2. **Create directory**: `.dev/<run>/generated/`.
3. **Detect Agent Teams**: `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` and the current session is interactive terminal Claude Code. If not satisfied → go to "Script 3: Agent Teams not enabled", wait for the user to choose one of three, and do not switch modes directly.
4. **Task Sizing**: rate per the table below, taking the highest tier hit.
5. **Four-trigger determination**: give `true/false` and evidence for each item.
6. **science_gate question**: ask the user with the four options A/B/C/D, default A (all off).
7. **Write `generated/init.md`**: write the result into `## N0 Precheck Determination` (format below).
8. **Route**:
   - XS/S → stop and fall back to single-agent mode, do not create `flow.json`.
   - M/L and `T1 && (T2 || T3 || T4)` → run `bash "${CLAUDE_PLUGIN_ROOT}/scripts/flow.sh" init --run "<run>"`, then run `bash "${CLAUDE_PLUGIN_ROOT}/scripts/flow.sh" set --science-gate-researcher <true|false> --science-gate-auditor <true|false>`.

## Task Sizing

| Tier | Determination (any hit takes the highest tier) | Destination |
|---|---|---|
| XS | ≤1 file and ≤30 lines and single behavior | fall back to single agent |
| S | 2–5 files or ≤150 lines; does not cross module interfaces | fall back to single agent |
| M | 6–20 files or 151–800 lines or crosses 2–3 modules | enter team |
| L | >20 files or >800 lines or crosses ≥4 modules/repos | enter team; N3 may split into waves |

Line count is estimated as "net added + net modified", excluding generated files and lock files.

## Four triggers

| ID | Condition | Evidence for true |
|---|---|---|
| T1 | scale reaches M/L | Task Sizing result is M or L |
| T2 | parallel benefit exists | `init.md` lists ≥2 preliminary work units and their `owned_files` drafts, pairwise disjoint |
| T3 | independent verification context needed | acceptance depends on any of: external fact audit, cross-module interface review, dual-axis review |
| T4 | user explicitly asks for a team | the user's own words contain one of "team formation / multi-agent / team / agent teams / parallel development" |

**Entry condition (hard-coded)**: `T1 && (T2 || T3 || T4)`. If any is unmet → do not enter the team workflow.

## science_gate four options

Use `AskUserQuestion` to ask one question (when unavailable, use an equivalent inline four-option prompt), ask only once:

> Does this requirement involve scientific algorithms, formulas, numerical conclusions, corpora/benchmark data, or a need to back user-claimed effects (e.g. "improves X%")?

| Option | researcher | auditor | Applicable | Written into `flow.json` |
|---|---|---|---|---|
| A (default) | false | false | routine engineering requirements with no external fact assertions | `{"researcher":false,"auditor":false}` |
| B | true | false | needs literature conclusions or corpora; implementation results need no scientific review | `{"researcher":true,"auditor":false}` |
| C | false | true | external scientific consensus exists to compare against, but no dedicated research is needed | `{"researcher":false,"auditor":true}` |
| D | true | true | scientific computing, algorithm implementation, paper reproduction, metric claims | `{"researcher":true,"auditor":true}` |

- Defaulting to A is deliberate: routine requirements do not pay the cost of the science channel.
- If the user changes the option during N1 → PM updates the booleans in `flow.json` and writes to `decisions.md`; N2 uses the latest values.
- Disabling or downgrading at runtime → must write `decisions.md` and obtain explicit user `confirmed`.

## Output format (written to `generated/init.md`)

```markdown
## N0 Precheck Determination

- Requirement directory: .dev/<run>
- run: <run>
- Agent Teams: available
- Task Sizing: M (8 files / 2 modules / ~400 lines)
- T1: true — M level
- T2: true — preliminary units U-01/U-02/U-03 have pairwise disjoint write sets
- Preliminary units: U-01(src/a.ts, tests/a.test.ts); U-02(src/b.ts, tests/b.test.ts); U-03(src/c.ts, tests/c.test.ts)
- T3: false
- T4: false
- Verdict: enter team workflow
- science_gate: A
- science_gate.researcher: false
- science_gate.auditor: false
- Determined at: YYYY-MM-DD
```

## Falling back to single-agent mode

Fallback must be an explicit action: state the tier and trigger results → present the alternative → ask whether to switch. Silent switching is forbidden.

### Script 1: XS/S or T1 not met

```
This requirement is rated [XS/S] by N0 ([file count] files / [module count] modules / ~[line count] lines),
below the M-level threshold, so team orchestration cost would exceed the benefit. Suggest switching to spec-coding-skill single-agent mode:
the Phase A→B gate, deviation logging, round review, and acceptance criteria stay the same. Switch now?
```

If `spec-coding-skill` is not installed (only this plugin is installed), change to:

```
Only leo-team-plugin is currently installed, so the single-agent skill is unavailable. Two options:
[A] Install leo-dev-plugin then use spec-coding-skill (/plugin install leo-dev-plugin@leo-cc-marketplace)
[B] I follow the same discipline directly: write the plan and wait for your confirmation, then implement, test, commit
```

### Script 2: T1 met but T2/T3/T4 all unmet

```
This requirement is [M/L] in scale, but no parallel benefit, independent verification need, or team
intent was found. A single agent can complete it continuously, and forming a team would only add 3–10× tokens.
Suggest switching to spec-coding-skill. Switch now?
```

### Script 3: Agent Teams not enabled (per `references/degradation.md`)

```
Agent Teams is not enabled; the following capabilities are unavailable:
- teammates cannot communicate directly (no mailbox)
- no SendMessage / TaskCreate collaboration tools
- teammate context is not persistent; each work unit must be re-initialized
Shared-file discipline, the state machine, hooks, and the acceptance flow still apply.

Please choose:
[A] Enable Agent Teams and restart the session (recommended; add
    "env": {"CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1"} to settings.json)
[B] Use subagents sequentially (saves tokens, no parallelism, rebuild context per unit)
[C] Fall back to single-agent spec-coding-skill
```

When the user chooses B: still proceed N0→N6, but in N3 cancel read-only overlap, run everything serialized, report back to `.team/<run>/verdicts/<unit>.json`, and write to `decisions.md`. When the user chooses C, this skill terminates immediately.

### User insists on forming a team for XS/S

Record in `decisions.md`:

```markdown
## D-<NNN> User overrides N0 sizing

- trigger: user_override
- decision: user requested a team for a [XS/S] requirement
- context: N0 rated [XS/S]; the 3–10× token cost was communicated
- approved_by: user
```

Execute with a minimal team: `spec-executor` + `spec-reviewer`, science channel fully off, N3 size `2`.

## Completion criteria

- `generated/init.md` contains `## N0 Precheck Determination`, all fields non-empty.
- `.team/<run>/flow.json` exists, `mission=planning`, `branch` non-empty, `science_gate` booleans match the user's option.
- When falling back to single agent: no `flow.json`, no branch, no spawn.
