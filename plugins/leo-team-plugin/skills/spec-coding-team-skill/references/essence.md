# Essence — Six Invariants

> This file is the **single source of truth** for the process. If `SKILL.md`, `phases/*`, or `agents/*` conflict with it, this file wins.
> All designs in the single-person `spec-coding-skill` can be traced back to these six invariants.

## I-1 Task grading, prevent over-engineering small work

Not every requirement is worth running the full process.

```
XS / S  → do not enter the team process; recommend falling back to single-person mode
M / L   → enter the team process
```

Forming a team has its own cost (official data: multiple agents consume 3–10× more tokens than a single agent). Grading is the first gate for cost control.

## I-2 Documents are state

Agents do not share memory with each other; they only share files.

- Not written to disk = did not happen
- "I assumed downstream knew" = collaboration failure
- Every decision, deviation, and rejected option must be readable from a file

## I-3 Phase A→B is a hard gate, cannot be delegated

Before user confirmation: no branch, no code, no team.

- Can only be initiated by the PM toward the user
- Cannot be asked by a teammate on the PM's behalf
- Cannot be skipped because "the user said something similar before"
- "Looks fine" is not confirmation; there must be an explicit `confirmed`

## I-4 No silent deviation

When plan and reality diverge, record and report; do not self-correct and act as if nothing happened.

- Deviations must be traceable (`findings.md` / `decisions.md`)
- Severe deviations must be adjudicated by the user
- Silently modifying the plan is a process failure, not an efficiency optimization

## I-5 Completion means verification

"It's written" is not complete; "verification passed" is.

- Verification and implementation must be in **different contexts** (verification subagent)
- Verification looks only at artifacts and acceptance criteria, not the author's reasoning
- `approved` (review passed) ≠ `merged` (in integration branch) ≠ `verified` (acceptance evidence complete)

## I-6 Round closure

Issues are not patched endlessly within one round; they are recorded and carried into the next round.

- Issues found this round → `findings.md`
- Has open issues → enter Round N+1 within the same session
- No open issues → proceed to integration acceptance
- Crossing sessions loses teammate context; this is a known limitation, not concealed

---

## Three Derived Rules

Operational rules derived from the six above that are easy to overlook:

| Derived rule | Source | Meaning |
|---|---|---|
| Split by write set, not by role; writes are serial | I-2 + I-5 | Work units split by `owned_files` boundaries; implementation units are always serial (global single claim); parallelism only occurs between read-only analysis and write operations; two same-named roles must not run in parallel |
| Verification separated from implementation | I-5 | reviewer / auditor do not participate in implementation and do not need implementation context |
| External content only enters research artifacts | I-2 + I-4 | `research.md` / `findings.md` are data zones; `team-plan.md` is the instruction zone; the two must not be mixed |
