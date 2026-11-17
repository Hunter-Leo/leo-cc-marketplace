# Decisions

> Purpose: append-only decision records: `D-<NNN>` process decisions, `ADR-<NNN>` architecture decisions, and `science_gate` change records.
> **Only the PM may write formal entries** (Status accepted / rejected / superseded). Others may only submit a proposal: Status `proposed`, Owner is themselves, awaiting PM adjudication.
> Accepted entries must not be edited; changes go through a new entry linked via `Supersedes`.

## D-<NNN> decision entries

Required for degradation, override, skipping a role, and accepting debt.

| ID | Trigger | Decision | Context | Alternatives | Consequences | Approved by |
|---|---|---|---|---|---|---|
| D-001 | <degradation \| override \| role_skipped \| debt_accepted \| phase_gate_confirmed> | <what was decided> | <background and constraints> | <rejected options and reasons> | <positive/negative consequences> | <user \| PM name> |

## science_gate change records

Required whenever the user changes the option during N1, and for any runtime downgrade.

| Time | researcher | auditor | Rationale | Changed by |
|---|---|---|---|---|
| <YYYY-MM-DD HH:MM> | <true \| false> | <true \| false> | <why the option changed> | <PM> |

## Decision table

| ID | Status | Trigger | Decision | Context | Alternatives | Consequences | Owner | Approved by | Supersedes |
|---|---|---|---|---|---|---|---|---|---|
| ADR-001 | <proposed \| accepted \| rejected \| superseded> | <triggering event> | <what was decided> | <background and constraints> | <rejected options and reasons> | <positive/negative consequences> | <name> | <PM name> | <ADR-000 \| —> |

## Complete example entry

### ADR-002 Replace database row locks with file locks

- **Status**: accepted
- **Trigger**: U-03 parallel write to <path> conflict, see F-IMP-04
- **Decision**: Use `flock` file locks, with lock granularity of a single owned_file
- **Context**: <the project is a single-machine CLI, no database; concurrent writes come from 2 parallel units>
- **Alternatives**:
  1. Database row locks: would introduce a new dependency, beyond this round's scope
  2. Serialize all units: loses parallelism benefits and is unnecessary
- **Consequences**: Positive is zero new dependencies and testable behavior; negative is it does not apply to cross-machine scenarios, which must be noted in README
- **Owner**: <name>
- **Approved by**: <PM name>
- **Supersedes**: —

## Proposal section (submitted by non-PM)

| ID | Status | Trigger | Decision | Context | Alternatives | Consequences | Owner | Approved by | Supersedes |
|---|---|---|---|---|---|---|---|---|---|
| ADR-003 | proposed | <trigger> | <proposed decision> | <background> | <alternatives> | <impact> | <name> | <pending> | — |
