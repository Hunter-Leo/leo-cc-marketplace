# Five Team-Level Invariants

> The six process invariants (`../../spec-coding-team-skill/references/essence.md`) govern "how the process proceeds"; these five govern "what must not break at team runtime".
> For how the shipped team process mechanically enforces these five, see `../../spec-coding-team-skill/references/team-invariants.md`. That file explains the implementation; this file remains the definition.
> Each must be mechanically checkable — items that cannot be checked by a script should be written to the "text layer" of `enforcement-ladder.md`, acknowledging that it is only a reminder.

---

## T-1 files over context

**Rule**: agents do not share memory, only files. No persisted file = it never happened.

- Decisions, deviations, excluded approaches, interface assumptions — all written into files.
- "I just said it in a message" does not constitute usable input for downstream.
- The mailbox carries only paths + a one-sentence conclusion, not content (`../../spec-coding-team-skill/references/rails.md` R-2).

**Consequence of violation**: facts disappear when resuming across sessions; two teammates have different memories of the same interface and both believe they are right; review cannot verify the upstream basis.

**Mechanical check**:

```bash
# Every unit that has left pending must have a persisted verdict/artifact file
jq -r '.units[] | select(.lane != "pending") | .id' .team/<run>/flow.json |
  while read -r id; do
    test -s ".team/<run>/verdicts/$id.json" || echo "MISSING: verdicts/$id.json"
  done
# A single message body > 2KB in the mailbox is a violation (should pass paths instead)
```

---

## T-2 own your files

**Rule**: write only paths declared in your own `Lane` section; must not edit other roles' artifacts.

- Parallel safety depends only on **whether the sets of written files intersect**; it has nothing to do with role names.
- When two people write the same file, the later writer overwrites the former without any error — this is the most insidious data loss.
- Shared files (`findings.md`, `decisions.md`) must have a single designated owner; others read-only or append through the owner.

**Consequence of violation**: silent overwrite, untraceable artifact versions, review sees "author artifacts" modified by others.

**Mechanical check**: run a set-intersection check once before parallel dispatch.

```bash
# This plugin's flow: directly validate owned_files of all units in .team/<run>/flow.json
bash "${CLAUDE_PLUGIN_ROOT}/scripts/check-lanes.sh"        # definite intersection exists → exit 1
bash "${CLAUDE_PLUGIN_ROOT}/scripts/check-lanes.sh" --json # machine-readable

# Non-plugin projects: write lanes as {"builder-a": ["src/a/**"], "builder-b": ["src/b/**"]},
# and use any set-intersection check (expand pairwise and intersect; non-empty → exit 1)
```

Enforcement chain: the role-card `## Lane` is documentation. Enforcement requires registering the same globs as the work unit (`flow.sh add-unit --files`) and taking the claim (`flow.sh claim --files`); the `PreToolUse` hook denies writes outside the active `claim.files` (`../../spec-coding-team-skill/references/rails.md` R-4).

---

## T-3 liveness is receipt

**Rule**: **only a SendMessage receipt from this session counts as "alive".**

None of the following **counts** as evidence of being alive:

| Looks like evidence | Why it does not count |
|---|---|
| artifact files on disk | may have been written in its last session, or by someone else |
| messages in an old inbox / mailbox | historical records, do not reflect the current process state |
| `status: running` in the registry | no heartbeat update since the last write; a stale snapshot |
| the last log line is seconds ago | may be idle waiting, or may already be finished |

The only valid evidence: **within this session, send a SendMessage to that teammate and receive a receipt**. No receipt = treated as dead (re-spawn or downgrade the task).

**Consequence of violation**: dispatch to a dead teammate and the task stays in `in_progress` forever; or accumulate messages to a non-responsive teammate, all lost on resume.

**Mechanical check**: ping before every dispatch.

```text
1. SendMessage(to: <name>, "ping") 
2. timeout (30s recommended) with no receipt → mark dead, do not enter pending
3. receipt received → dispatch is allowed
```

Note: this rule costs one extra round trip per dispatch. What it buys is "never hand work to someone who does not exist".

---

## T-4 keep checkpoint

**Rule**: at the end of every work unit (regardless of PASS / FAIL / BLOCKED), a snapshot must be written with four fixed items:

```yaml
unit: <id>
state: <state after transition>
done: [completed verifiable items]
open: [open questions, with owner]
next: <next action, with recipient>
```

**Consequence of violation**: cannot tell which work is complete after an interrupted session; redo work or miss open items on resume; "I thought it was done".

**Mechanical check**:

```bash
# Every non-terminal unit must have a snapshot, and the latest snapshot must not be earlier than the unit's last state change
bash "${CLAUDE_PLUGIN_ROOT}/scripts/flow.sh" checkpoint --note "unit <id> done"
ls -t .team/<run>/snapshots/*.json | head -1     # take the latest snapshot, compare with the last timestamp in flow.json.events
```

---

## T-5 lead coordinates

**Rule**: team-level decisions can only be made by the lead — decomposition, number of roles, whether to enter the next round, whether to escalate to the user for adjudication.

Teammates may propose, veto, and report, but **must not change the team structure themselves**.

**Consequence of violation**: two agents each adjust the decomposition, causing overlapping responsibilities or gaps with no owner; the gate is asked on the lead's behalf, and the object of user confirmation shifts (`../../spec-coding-team-skill/references/essence.md` I-3).

**Mechanical check**:

- Write permission to `team-plan.md` / `tasks.md` / `decisions.md` is granted only to the lead; `PreToolUse` rejects other roles directly.
- Derived roles (agents spawned by teammates themselves) are all treated as having no coordination permission; their output must be returned to the lead before entering the plan.

---

## Relationship Among the Five

| If broken | Causes cascading |
|---|---|
| T-1 | T-4's snapshot has no basis, T-5's adjudication cannot be verified |
| T-2 | T-1's files are untrustworthy (unknown who wrote them), and T-3 review cannot locate the responsible party |
| T-3 | tasks assigned to dead processes, T-4's `open` hangs forever |
| T-4 | T-3 cannot determine who is dead, T-5 cannot decide the next step |
| T-5 | decomposition changes arbitrarily, T-2's lane declarations become invalid |

The five are not a checklist but a loop: if any one breaks, checking the other four will produce false signals.
