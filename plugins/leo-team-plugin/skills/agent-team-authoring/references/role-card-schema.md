# Role Card Schema — 11 Fields

> A role card = a contract readable by scripts and hooks.
> Test: **remove any section — will the role start guessing?** If it guesses, the section cannot be deleted.

## 0. File-level Prerequisite: frontmatter

```yaml
---
name: <kebab-case, unique across the team>
description: <2–4 trigger scenarios — when this role should be used>
tools: <minimal tool surface, comma-separated>
model: <chosen by task complexity>
color: <UI distinction only>
---
```

| Field | What to write | Common mistakes |
|---|---|---|
| `name` | lowercase hyphenated; unique within the team and referenceable by the primer | same name as the archetype, making two builders indistinguishable |
| `description` | **2–4 trigger scenarios**, write "when to use me", not "how great I am" | only a responsibility description, so the scheduler cannot tell whether to wake it |
| `tools` | the fewer the better; decide the archetype first, then trim | all granted by default, over-privileged |
| `model` | chosen by reasoning difficulty; do not downgrade verification roles | trying to use a bigger model to compensate for defects in the role card itself |
| `color` | pure UI distinction | using color to imply capability differences (see prohibitions at the end) |

`description` example (acceptable): `Use when you need to judge whether the implementation meets the acceptance criteria and need an uninvolved third party to provide evidence.`

## 1. Identity

**What to write**: one sentence stating "who you are + what you are responsible for". Identity is a responsibility boundary, not a persona.

**Counterexample**: `You are a senior full-stack architect with 15 years of experience, proficient in frontend, backend and DevOps, with a rigorous personality...`

**Length**: ≤ 2 lines. More than 2 lines means you are writing a persona, not a responsibility.

## 2. Lane

**What to write**: two sets of paths — writable (glob list) and read-only (glob list), machine-parsable. The `## Lane` section is documentation. Enforcement requires registering the same globs as the work unit (`flow.sh add-unit --files`) and taking the claim (`flow.sh claim --files`); the `PreToolUse` hook denies writes outside the active `claim.files`.

**Counterexample**: `Responsible for the frontend part and related test files.`

**Length**: 1–5 globs for writable; read-only may be omitted (default all-repo read-only). One per line, no explanatory prose.

## 3. Inputs

**What to write**: the exact paths of upstream artifacts, plus **behavior when missing**. Behavior when missing may only be "output BLOCKED and stop"; no guessing or filling in.

**Counterexample**: `Refer to the upstream design document.` (Which one? What if missing?)

**Length**: ≤ 5 items. Each in the form `- <path> — <what it provides> — BLOCKED if missing`.

## 4. Procedure

**What to write**: 5–9 ordered steps, each with an observable action (read some file, run some command, write some file). No "then think about it" between steps.

**Counterexample**: `1. Understand requirements 2. Analyze code 3. Implement 4. Test 5. Done`

**Length**: 5–9 steps, each ≤ 2 lines. If more than 9, consider splitting the role or putting details in references.

## 5. Prohibitions

**What to write**: explicitly forbidden actions. Prohibition is more effective than encouragement: the model finds reasons for "should do", but "must not" is a hard boundary.

**Counterexample**: `Please try not to modify other modules.` ("try" = permitted)

**Length**: 3–7 items. Include at least one path boundary, one "must not self-review", and one "must not deviate silently".

## 6. Output contract

**What to write**: artifact persistence path + fixed return format. The return format is consistent with `../../spec-coding-team-skill/references/rails.md` R-10; field names must not be changed.

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

**Counterexample**: `Tell me the result when done.`

**Verdict file**: while a claim is active, also persist `.team/<run>/verdicts/<unit-id>.json` containing at least `{verdict, artifacts, stop_reason}`. Conversation-only returns are blocked by the `SubagentStop` hook.

**Length**: 1–3 paths + one copy of the code block above. Field names are fixed; do not add or remove.

## 7. Done criteria

**What to write**: executable judgment — command + expected output or threshold. The judgment must be re-runnable by a third party who does not know the implementation process.

**Counterexample**: `Functionality normal, code clean, tests pass.`

**Length**: 2–6 items. Each contains a command or a numeric threshold.

## 8. Escalation

**What to write**: when to stop, whom to report to, what to report. Must include the stop conditions of `../../spec-coding-team-skill/references/rails.md` R-9 (especially "third failure of the same unit").

**Counterexample**: `Communicate promptly when issues arise.`

**Length**: 3–5 items. Each in the form `- <trigger condition> → report <field> to <role>`.

## 9. Rails

**What to write**: only a one-line reference: `See ../../spec-coding-team-skill/references/rails.md` (adjust according to the actual hierarchy after deployment to the team directory). If a claim is active, the role must also persist its verdict file; see section 6.

**Counterexample**: copying R-1 to R-11 into the role card (copies will diverge and consume budget).

**Length**: 1 line. Copying any content is a mistake.

## 10. Context budget

**What to write**: the size cap for file reads, sharding strategy, max number of files per read. Aligns with `../../spec-coding-team-skill/references/rails.md` R-6.

**Counterexample**: `Pay attention to controlling context length.` (not executable)

**Length**: 3–5 lines, or a 3-row table (≤200KB read fully / 200–500KB grep first / >1MB search only and record skipped).

## 11. Anti-patterns

**What to write**: failure modes **specific to this role**, one sentence each, preferably with an observable signal.

**Counterexample**: `Be careful not to make mistakes.`

**Length**: 3–5 items. At least one from something that actually happened to this role in this project; when there is no real case, write "to be observed", but do not write generic entries.

---

## Explicitly Prohibited

| Prohibited | Reason |
|---|---|
| **Long persona** | consumes context budget and has no binding force on behavior; the model will not be more rigorous because of "a rigorous personality" |
| **"15 years of experience" personas** | an unverifiable claim that only induces the model to output more confidently rather than more accurately |
| **Using `color` to express capability** | color is only a UI label; using it to imply "this role is stronger" makes the scheduler weight incorrectly |
| **Copying rails content** | multiple copies necessarily diverge; shared discipline can have only one source of truth |
| **Writing business solutions in the role card** | the role card is a constraint; solutions belong in `team-plan.md`; mixing makes the solution be treated as a constraint on reload |

## Self-Check for an Acceptable Role Card

- Take the 11 headings alone and you can see what this role **cannot** do.
- If any section is deleted, the role needs to guess — so not one section can be missing.
- Read through: not a single sentence describes "this person"; all describe "this job".
