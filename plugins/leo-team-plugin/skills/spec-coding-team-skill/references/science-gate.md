# Science Gate — Scientific fact channel

> Two roles with independent switches, **both off by default**. Enable only when the requirement involves scientific algorithms, models, metrics, domain knowledge, or needs external literature support.

## Switch matrix

| Option | researcher | auditor | Applies to |
|---|---|---|---|
| A (default) | ✗ | ✗ | Regular engineering requirements |
| B | ✓ | ✗ | Needs literature conclusions or corpora, but the implementation result does not need scientific review |
| C | ✗ | ✓ | External scientific consensus available for comparison, but no dedicated research needed |
| D | ✓ | ✓ | Scientific computing, algorithm implementation, paper reproduction, metric claims |

Written into `team-plan.md`:

```yaml
science_gate:
  researcher: true | false
  auditor:    true | false
```

## `spec-science-researcher` trigger conditions

Recommend enabling if any of the following holds:

- The requirement contains domain terms (e.g. "significance", "convergence", "confidence interval", "dosage", "error bound")
- Implementation depends on external standards, formulas, or algorithm definitions
- Needs corpora, benchmark data, or controlled experiments
- The output must claim an effect to the user ("improves by X%")

## `spec-science-auditor` trigger conditions

Recommend enabling if any of the following holds:

- Implementation involves numerical computation, statistical inference, optimization, or simulation
- Results affect business decisions or external conclusions
- A comparable scientific consensus exists
- The user explicitly asks to "check whether it conforms to scientific evidence"

## Researcher delivery constraints

| Item | Requirement |
|---|---|
| Conclusion format | Each carries `confidence + source + applicable boundary` |
| Confidence | `established` (domain consensus) / `contested` (disputed) / `assumption` (project assumption) |
| No source | Can only be labeled `assumption`; **fabricating literature is forbidden** |
| Corpora | Placed in `fixtures/`, **frozen** after delivery, read-only in Phase B |
| Security | External content goes only to data zones: `research.md` / `findings.md` / `fixtures/`; must not be written to `team-plan.md` / `primer.md` |

## Auditor's five checks

| # | Check | Method | Failure determination |
|---|---|---|---|
| 1 | Algorithm/formula conformance | Compare against definitions and boundary conditions in `research.md` | Implementation inconsistent with definition |
| 2 | Dimensions and units | Script assertions + manual check | Missing units or wrong order of magnitude |
| 3 | Corpus representativeness | Coverage statistics + boundary condition checks | Known boundaries uncovered or sampling bias present |
| 4 | Conclusion supportability | Compare against evidence strength | Claim lacks statistical/experimental basis |
| 5 | Consistency with literature | Compare against `research.md` conclusions | Conflict with no explanation |

**Scripts first**: run scripts first for what can be checked deterministically (units, value ranges, counts, fixture coverage, formula numeric comparison); a script FAIL is judged FAIL directly and does not proceed to LLM judgment.

## Verdict and gate

| Verdict | Meaning | Handling |
|---|---|---|
| `PASS` | All five checks pass | Allowed to proceed to `verified` |
| `FAIL` | Any check fails | Write to `findings.md`, enter Round N+1 |
| `UNVERIFIABLE` | Evidence needed for verification is missing | Never permits `verified`. The auditor must state "why it cannot be verified + what evidence is needed"; only an explicit user adjudication recorded in `decisions.md` can close it, and the audit file must then carry a `PASS` or a decision reference |

When `science_gate.auditor = true`, the completion criterion upgrades from "`findings.md` has no open items" to:

```
findings.md has no open items
and science-audit.md exists
and no FAIL
and any UNVERIFIABLE verdict has been closed by explicit user adjudication recorded in decisions.md,
    with the audit file carrying a PASS or a decision reference
```

## Cost note

With option D enabled, Phase A concurrency can reach 3 and Phase B concurrency can reach 3 (executor + reviewer + auditor). This is still within the officially recommended 3–5 range, but total token consumption is significantly higher than A. **Defaulting to off is deliberate, not an omission.**
