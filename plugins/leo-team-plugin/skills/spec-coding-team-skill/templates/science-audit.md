# Science Audit

> Purpose: audit record for independently verifying research conclusions and numerical correctness, written exclusively by the auditor.
> The auditor does not participate in implementation and does not read the implementer's reasoning; it looks only at artifacts and evidence (essence I-5).
> Issues found are recorded as `F-AUD-*` in findings.md and are not discussed at length in this file.

## Metadata

| Field | Value |
|---|---|
| audit_id | <AUD-001> |
| auditor | <name> |
| round | <N> |
| scope | <audit target: research.md R-x / module path> |
| audited_at | <YYYY-MM-DD HH:MM> |

## 1. Script-first section

Run deterministic scripts first, then make manual judgments. Record the actual command and exit code for each item; do not just write "already run".

| # | Script / command | Input | Exit code | Key output | Result |
|---|---|---|---|---|---|
| 1 | <e.g. uv run pytest tests/science -q> | <path> | <0> | <N passed> | <PASS \| FAIL> |
| 2 | <e.g. python scripts/check_units.py> | <path> | <0> | <all units consistent> | <PASS \| FAIL> |
| 3 | <e.g. python scripts/verify_formula.py> | <path> | <1> | <mismatch at term 3> | <FAIL> |

- Reason no scripts were run: <none / explain why running was impossible>
- Credibility issues with the scripts themselves: <none / explain>
- Skipped checks: <none / what was skipped and why (rails R-6)>

## 2. Check matrix

Fixed five items; do not add or remove any.

| Check item | Method | Result | Evidence |
|---|---|---|---|
| Algorithm/formula conformance | <compare each formula against source and implementation location> | <PASS \| FAIL \| UNVERIFIABLE> | <file:line / source page number> |
| Dimensions and units | <dimension-by-dimension derivation / unit check script> | <PASS \| FAIL \| UNVERIFIABLE> | <command output / file:line> |
| Corpus representativeness | <sample source, scale, coverage> | <PASS \| FAIL \| UNVERIFIABLE> | <data path / statistics> |
| Conclusion supportability | <conclusion → evidence item-by-item mapping> | <PASS \| FAIL \| UNVERIFIABLE> | <research.md R-n> |
| Consistency with literature | <compare with source numerical or qualitative conclusions> | <PASS \| FAIL \| UNVERIFIABLE> | <DOI / URL> |

## 3. UNVERIFIABLE explanation

Required for any check item judged UNVERIFIABLE; missing one is treated as an incomplete audit.

| Check item | Why it cannot be verified | What evidence is needed | Who can provide it |
|---|---|---|---|
| <check item> | <specific reason> | <evidence format and source requirements> | <role / user> |

## 4. Final verdict

- **Verdict**: <PASS | FAIL | UNVERIFIABLE>
- An `UNVERIFIABLE` verdict never permits `verified`; only explicit user adjudication recorded in `decisions.md` can close it, and this file must then carry a `PASS` or a decision reference
- Passed items: <list check items>
- Failed items: <list check items + corresponding findings ID>
- Blocks entering the next phase: <yes \| no, with a one-line reason>
- Auditor signature: <name> @ <YYYY-MM-DD HH:MM>
