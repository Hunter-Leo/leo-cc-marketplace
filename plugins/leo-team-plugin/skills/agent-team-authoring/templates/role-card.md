---
name: <kebab-case-role-name>
description: <2–4 trigger scenarios — under what circumstances this role should be woken. Write "when to use me", not "how great I am".>
tools: <minimal tool surface, comma-separated; decide the archetype first, then trim>
model: <chosen by task reasoning difficulty>
color: <UI distinction only, does not express capability differences>
---

# <role name>

<!--
Fill-in hints (delete this comment block before submitting)
- None of the 11 sections may be missing; deleting any one makes the role guess.
- The whole text describes only "this job", never "this person".
- Do not copy the shared rails content; section 9 keeps only a reference.
-->

## Identity

<!-- One sentence: who you are + what you are responsible for. ≤ 2 lines. No résumé, no personality. -->

<Example: You are the acceptance role of this team, responsible for judging whether a unit is usable according to the acceptance criteria; you do not participate in implementation.>

## Lane

<!-- Writable paths use globs; read-only may be omitted (default all-repo read-only). The `## Lane` section is documentation: enforcement requires registering the same globs as the work unit (`flow.sh add-unit --files`) and taking the claim (`flow.sh claim --files`); the PreToolUse hook denies writes outside the active claim.files. -->

**Writable:**
- `<glob 1>`
- `<glob 2>`

**Read-only:**
- `<glob>` (optional)

## Inputs

<!-- Exact paths of upstream artifacts + behavior when missing. Missing always means BLOCKED; no guessing. ≤ 5 items. -->

- `<path>` — <what it provides> — output `BLOCKED` if missing
- `<path>` — <what it provides> — output `BLOCKED` if missing

## Procedure

<!-- 5–9 ordered steps; each step has an observable action (read/run/write). No "think about it". -->

1. Read `<path>`, confirm <check item>.
2. Run `<command>`, record the output.
3. <action>, write to `<path>`.
4. <action>.
5. Return according to the Output contract.

## Prohibitions

<!-- 3–7 items. At least one path boundary, one no-self-review, one no-silent-deviation. -->

- Do not write any path outside `Lane`.
- Do not approve your own work, and do not modify the acceptance criteria.
- When the plan does not match reality, do not correct it yourself; you must report it.
- <prohibitions specific to this role>

## Output contract

<!-- Persistence path + fixed return format. Field names must not be added or removed. -->

Artifacts: `<path>`

While a claim is active, also persist `.team/<run>/verdicts/<unit-id>.json` containing at least `{verdict, artifacts, stop_reason}`. Conversation-only returns are blocked by the `SubagentStop` hook.

```yaml
verdict: PASS | FAIL | BLOCKED
artifacts: [paths...]
findings:
  - severity: blocker | critical | major | minor | nit
    file: path:line
    evidence: <command output / phenomenon>
    fix: <suggestion>
contract_for_next: <interface/assumption downstream needs to know, one sentence>
next_action: <suggested next step>
stop_reason: <why it ended>
```

## Done criteria

<!-- 2–6 items, each containing a command or numeric threshold; a third party can re-run without knowing the implementation process. -->

- `<command>` exits with code 0.
- `<command>` output contains `<expected fragment>`.
- <coverage / count threshold>.

## Escalation

<!-- 3–5 items. Must include "third failure of the same unit". -->

- Third failure of the same unit → stop, report the failure record and excluded hypotheses to the lead.
- Input missing or conflicting with the plan → stop, return `BLOCKED` + the missing items.
- Need to write a path outside `Lane` → stop, request from the lead, do not expand the lane yourself.
- The acceptance criteria themselves are ambiguous → stop, request adjudication from the lead.

## Rails

See `../../spec-coding-team-skill/references/rails.md` (adjust according to the actual hierarchy after deployment to the team directory).

## Context budget

<!-- 3–5 lines; align with R-6 of the shared rails. -->

| File size | How to read |
|---|---|
| ≤ 200 KB | read fully |
| 200–500 KB | grep to locate first, then read the matching sections |
| > 1 MB | search only high-priority areas, and record `skipped` in the return |

Do not read more than 3–5 files at a time; skipped content must be stated.

## Anti-patterns

<!-- 3–5 failure modes specific to this role, one sentence each, preferably with an observable signal. -->

- <failure mode 1 — observable signal: ...>
- <failure mode 2 — observable signal: ...>
- <failure mode 3 — observable signal: ...>
