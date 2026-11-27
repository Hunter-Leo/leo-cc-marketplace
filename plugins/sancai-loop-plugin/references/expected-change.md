# Expected Change Protocol (Sancai)

> A failing test is a question, not an instruction. Decide whether the code,
> the oracle, the behavior, or the corpus is wrong before changing anything.

## Why

Historical tests encode past decisions. When a requirement intentionally
changes behavior, a golden file, or a corpus, the old expectation must change
too. Without a protocol, the easiest path is to edit the expected value until
the suite turns green. That destroys the test's value and hides regressions.

Sancai makes the change explicit, scoped, and independently reviewed.

## Flow

```text
H1  intent.test_policy        how to run tests and coverage
    intent.change_policy      which paths are protected and who may change them
              │
              ▼
L1  executor sees a failing historical test
              │
              ├─ code is wrong ──────────────► fix code, no EC
              ├─ oracle is wrong ────────────► fix test + proof, no EC
              └─ behavior/corpus changed ────► sancai_change.py propose
                                                        │
                                                        ▼
L2  G0  freeze EC drafts ──► run tests ──► classify failures ──► evidence
              │
              ▼
G3  verifier checks traceability, scope, oracle independence, impact, rollback
              │
              ▼
H3  human accepts the new baseline
```

## H1 policy

```json
{
  "test_policy": {
    "command": "python3 tools/run_tests.py --report .sancai/runs/<run>/L2-harness/test-report.json",
    "report": ".sancai/runs/<run>/L2-harness/test-report.json",
    "timeout_seconds": 1800,
    "coverage": {
      "command": "python3 tools/run_coverage.py --report .sancai/runs/<run>/L2-harness/coverage.json",
      "report": ".sancai/runs/<run>/L2-harness/coverage.json",
      "core_globs": ["src/core/**"],
      "minimum_core_percent": 80,
      "enforce": true
    }
  },
  "change_policy": {
    "expected_change_allowed": true,
    "protected_globs": ["tests/golden/**", "corpus/**"],
    "max_changed_files": 20,
    "science_audit_above": 0,
    "baseline_id": "corpus-2026-01",
    "require_rollback_plan": true
  }
}
```

Both policies are optional. Without `test_policy`, G0 runs only the acceptance
and hidden checks. Without `change_policy`, no protected-path checks run. This
keeps legacy intents byte-compatible.

`report` paths must be under `.sancai/runs/<run>/L2-harness/`; a report under
L1 would be writable by the executor.

The report itself must be JSON in the shapes below. A project adapter (for
example, a pytest plugin wrapper) is responsible for producing it.

### Test report shape

```json
{
  "tests": [
    {"id": "tests/test_auth.py::test_login", "outcome": "passed"},
    {"id": "tests/test_legacy.py::test_old_format", "outcome": "failed"}
  ],
  "summary": {"total": 2, "passed": 1, "failed": 1, "skipped": 0}
}
```

`id` or `nodeid` is accepted; `outcome` or `result` is accepted. A malformed
report fails closed when a policy expects one.

### Coverage report shape

```json
{
  "files": {
    "src/core/auth.py": {
      "summary": {"covered_lines": 90, "num_statements": 100}
    }
  }
}
```

Coverage is statement-weighted over files matching `core_globs`. A missing core
file counts as 0%.

## Expected-change proposal

The executor submits a draft through the harness; it never writes `.sancai/`
directly:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/sancai_change.py" propose \
  --run <run> --wo <WO-ID> --file EC-001.json
```

Draft location:

```text
.sancai/runs/<run>/L1-code/expected-changes/<WO>/EC-001.json
```

Write the source draft outside `change_policy.protected_globs` and delete it
after `propose` succeeds. G0 counts untracked files in `changed_files`, so a
draft left beside protected fixtures can look like an undeclared change.

Frozen manifest:

```text
.sancai/runs/<run>/L2-harness/expected-changes/<WO>/manifest.json
```

G0 freezes the draft before running tests. G3 compares the live draft and the
stored manifest before rerunning G0. A post-freeze edit blocks the Work Order.

### EC schema

```json
{
  "id": "EC-001",
  "wo": "WO-001",
  "type": "behavior_change",
  "req": "REQ-001",
  "ac": ["AC-1"],
  "reason": "the new format removes the legacy delimiter",
  "scope": ["tests/golden/**"],
  "old_baseline": "corpus-2025-12",
  "new_baseline": "corpus-2026-01",
  "affected_cases": 2,
  "oracle": "semantic",
  "oracle_ref": "docs/format-v2.md#section-3",
  "expected_failures": ["tests/test_legacy.py::test_old_format"],
  "backward_compatible": false,
  "migration": "run scripts/migrate_corpus.py",
  "rollback": "restore corpus-2025-12 and revert the reader"
}
```

Required: `id`, `wo`, `type`, `reason`, `ac`, `scope`, `affected_cases`,
`oracle`, `oracle_ref`, `backward_compatible`. `rollback` is required when
`change_policy.require_rollback_plan` is true.

`type`:

- `behavior_change` — intended observable behavior changed.
- `oracle_fix` — the old test encoded the wrong expectation.
- `corpus_rebaseline` — the corpus, labels, or golden data changed.

`oracle`:

| Type | Meaning | Example |
|---|---|---|
| `exact` | byte/string equality | JSON snapshot |
| `semantic` | normalized/structural equality | parsed AST or sorted output |
| `property` | invariant holds for all inputs | round-trip encode/decode |
| `statistical` | distribution or threshold | precision ≥ 0.92 on a fixed set |
| `human` | named human decision | product spec, review note |

`affected_cases` is the **number of changed protected files** matched by
`scope`. It is computed, not taken on trust. A rename counts as old and new; a
binary file counts as one. `max_changed_files` caps the union of changed
protected files across ECs.

The executor cannot write `approved`, `approved_by`, or `approved_at`. Approval
is derived from `change_policy.expected_change_allowed`; the human accepts the
new baseline at H3.

## G0 classification

| Observation | Classification | Result |
|---|---|---|
| Protected path changed, no EC | integrity violation | `blocked` |
| EC scope misses a protected path | integrity violation | `blocked` |
| `affected_cases` underreported | integrity violation | `blocked` |
| `max_changed_files` exceeded | integrity violation | `blocked` |
| Live EC differs from frozen manifest | tamper | `blocked` |
| Declared failure did not occur | stale expectation | `changes_requested` |
| Failure not declared by any EC | regression | `changes_requested` |
| Report malformed or command timed out | invalid evidence | `changes_requested` |
| Coverage below threshold | coverage failure | `changes_requested` |

`expected_failures` names test ids from the structured report. A declared but
absent failure is stale; an undeclared failure is a regression. Both fail G0.

## Science routing

A `corpus_rebaseline`, or an EC count at/above `science_audit_above`, requires a
science audit. The audit must list the frozen EC ids; an audit for a different
set is `blocked`. `science_audit_above: 0` means every EC; omitting it disables
the count trigger.

## Anti-patterns

- Updating a golden file because the test failed.
- Declaring `affected_cases: 1` for a directory-wide change.
- Writing an EC after G0 and expecting the gate to accept it.
- Using `oracle: exact` when only a semantic property is stable.
- A `corpus_rebaseline` without an independent oracle or science audit.
- Approving an EC from inside the executor.
