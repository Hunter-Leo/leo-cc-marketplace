# Degradation — Fallback path when Agent Teams is disabled

> Iron rule: **no silent degradation**. You must explicitly tell the user what is lost and let them choose.

## Detection

```bash
[ "${CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS:-0}" = "1" ] && echo teams || echo subagent
```

- Only effective in **interactive sessions**. `claude -p` and the Agent SDK do not spawn teammates even if the variable is 1
- Where to set it: the `env` section of `~/.claude/settings.json` or the project's `.claude/settings.json`, or a shell export

## Notification template when disabled

```markdown
Agent Teams is detected as not enabled; subagent mode will be used, and the following capabilities are unavailable:

- ❌ Teammates cannot communicate directly (no mailbox)
- ❌ No collaboration tools such as SendMessage / TaskCreate
- ❌ Teammate context is not persistent; every work unit must be re-initialized
- ✅ Shared-file discipline, state machine, hooks, and acceptance process **remain fully in effect**

Please choose:
[A] Enable Agent Teams and restart the session (recommended)
    Add "env": {"CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1"} to settings.json
[B] Execute sequentially with subagents (saves tokens, but rebuilds context per unit)
[C] Fall back to single-person mode (spec-coding-skill; if not installed, execute directly)
```

> If `spec-coding-skill` is unavailable (only `leo-team-plugin` is installed), option C becomes "execute directly under the same discipline: produce a plan and wait for confirmation, then implement, test, and commit", or prompt to install `leo-dev-plugin`.

## Capability comparison of the three modes

| Capability | Teams | subagent | Single-person |
|---|---|---|---|
| Teammate context persistent | ✓ | ✗ | — |
| Direct teammate communication | ✓ | ✗ | — |
| Shared task list | ✓ | Partial | ✗ |
| Shared-file discipline | ✓ | ✓ | ✓ |
| State machine + hooks | ✓ | ✓ | ✓ |
| Black-box verification (reviewer / auditor) | ✓ | ✓ | Weakened |

## Behavioral differences after degradation

| Item | Difference | Response |
|---|---|---|
| Context | Each work unit re-reads `primer.md` + its own input files | Provide a self-contained input list in the spawn prompt |
| Handoff | No mailbox; everything goes through files | Define the report contract as the file `.team/<run>/verdicts/<unit>.json` |
| Parallelism | Sequential execution only (subagents do not share state) | At N3 team formation, cancel read-only overlap; all serial |
| Checkpoint | No session resume | Rely on `handoff.md` + `dead-ends.md` |
| Review persistence | The harness may reject subagent writes to `findings.md` / report-type files | Use `.team/<run>/verdicts/<unit>-review.json` as the authoritative record; when the PM transcribes it into `findings.md`, it must annotate the source and must not rewrite conclusions or downgrade severity |

## Prohibitions

- ❌ Using subagents without notifying the user
- ❌ Claiming "the effect is the same"
- ❌ Pretending a team was formed in `-p` mode
- ❌ Defaulting to B for convenience
