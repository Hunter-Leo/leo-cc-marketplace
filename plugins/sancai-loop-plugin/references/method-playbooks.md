# Method Playbooks (Sancai)

> Methods are triggers, not phases. Use one when its condition is met; record
> why you used it or why you skipped it.

## Term grilling + ADR

**Trigger:** ambiguous domain term, irreversible decision, architecture change,
interface contract, or data model change.

**Output:** a short term definition in `design.md`, and an ADR when the decision
is architectural or hard to reverse.

**Skip:** only when the term is already defined in the intent or an existing ADR.

## Vertical-slice TDD

**Trigger:** a feature with observable behavior and executable acceptance criteria.

**Output:** one thin end-to-end slice per cycle: test -> implement -> verify.

**Skip:** for pure refactors, documentation, or changes without behavior.

## Dual-axis review

**Trigger:** security, concurrency, data migration, or high-blast-radius change.

**Output:** two independent review axes: correctness/behavior, and
security/operability. Each axis records findings separately.

**Skip:** for XS changes with no security or data impact.

## Architecture deepening

**Trigger:** repeated coupling, duplicated logic across Work Orders, or a module
that is hard to test through its public interface.

**Output:** a refactor Work Order with a before/after dependency diagram and a
behavior-preservation test.

**Skip:** when the duplication is local and removing it would add speculative
abstraction.

## Structured debugging

**Trigger:** a failure that cannot be explained from logs or a single test.

**Output:** a written hypothesis, the smallest reproduction, the observed
result, and the root cause. Record the failed hypotheses in `issues.md`.

**Skip:** for known failures with an obvious cause.

## Recording

Add one line to `design.md` or `issues.md`:

```text
Method: vertical-slice TDD
Why: AC-2 has observable behavior and an executable check.
Skipped: dual-axis review (no security or data impact).
```
