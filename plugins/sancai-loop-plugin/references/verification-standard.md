# Verification Standard (Sancai)

> G0 decides whether the Work Order is ready for review. G3 decides whether it
> is verified. Neither step trusts narration; both trust evidence.

## G0 — executor gate

Before submitting a Work Order:

- [ ] Formatter and linter pass.
- [ ] `test_policy.command` passes, or every failure is declared by a frozen
      expected change. No unclassified failure or stale expectation.
- [ ] `test_policy.coverage` meets `minimum_core_percent` when enforced.
- [ ] New behavior has normal, edge, and error tests.
- [ ] Every changed protected path is covered by an expected-change (EC) draft.
- [ ] Core logic coverage is at least 80%, or the gap is justified in `design.md`.
- [ ] Public APIs have type annotations and docstrings.
- [ ] No secret, token, or environment value is written to evidence.
- [ ] The diff stays inside `owned_files`.
- [ ] No test is skipped, weakened, or replaced by a stub.

G0 evidence is harness-owned. The executor may run checks; it may not write or
edit `evidence/` or `verdicts/`.

## G3 — independent verification

The verifier receives only:

- `L2-harness/evidence/<WO>.json`, including `tests`, `coverage`,
  `protected_changes`, and the frozen `expected_changes` snapshot
- the acceptance criteria, `science`, `test_policy`, and `change_policy` from
  `intent.json`
- the diff
- the relevant standards (`design-principles`, `data-model`, `comment`,
  `verification`, `expected-change`)

The verifier must not read the executor's report, narrative, or reasoning.

Checks:

1. Every acceptance criterion has evidence.
2. Every deterministic check actually ran and passed; exit codes are inspected.
3. Negative invariants hold for deletion-type requirements.
4. Evidence hashes match the artifacts.
5. No test weakening, skipped tests, or stubs.
6. The diff stays inside `owned_files`.
7. Public interfaces are typed and documented.
8. Data model changes have a schema version and migration plan.
9. OOP/SOLID deviations are documented and justified.
10. Comments explain why and match the code.
11. Science routing: a required audit exists and passes; a numeric or
    statistical claim without routing is a `major` finding.
12. Test execution: the policy command ran, did not time out, and produced a
    valid report; no skipped, weakened, or stub tests.
13. Coverage: the core percentage meets the enforced threshold, or the gap is
    justified.
14. Test quality: normal, edge, and error cases; public interfaces; mocks only
    at system boundaries.
15. Expected-change traceability: every EC binds a requirement (when selected)
    and the AC it changes.
16. Expected-change scope: every protected change is covered, and
    `affected_cases` matches `applies_to`.
17. Oracle independence: the new expectation is not merely the current output.
18. Impact and rollback: `affected_cases` is honest; breaking changes have a
    migration plan and, when required, a rollback plan.
19. Corpus/science routing: corpus, label, golden, or statistical changes
    trigger an audit that covers the EC ids.

Verdict rules:

- `pass` only when every AC is satisfied and there are no blocker/critical findings.
- Missing evidence means `fail`; do not guess.
- Unverifiable claims fail closed.
- Never edit code to make it pass.

## Test standard

### Required cases

Every behavior change covers:

- Normal case: the expected path.
- Edge case: empty, maximum, boundary, duplicate, or partial input.
- Error case: invalid input, missing dependency, timeout, or permission denial.

### Behavior, not implementation

Test through the public interface. A test should survive an internal refactor.
Do not test private methods, call counts, or call order.

### Mock discipline

Mock only at system boundaries:

- External APIs.
- Databases (prefer a test database).
- Time and randomness.
- Filesystem when it is not the behavior under test.
- Third-party services unavailable in the test environment.

Do not mock your own classes, modules, or internal collaborators.

### Coverage

- Core logic: at least 80%.
- Security gates and state transitions: adversarial tests, not just line coverage.
- A coverage exception must be written in `design.md` with a reason.

### Anti-patterns

- Testing private methods.
- Asserting on call count or call order.
- Bypassing the interface to inspect internals.
- One test asserting many unrelated things.
- Test names that describe implementation instead of behavior.
- Weakening an assertion to make a failing test pass.

## Expected changes

A test failure is not automatically a regression. Classify it:

| Cause | Action |
|---|---|
| Code is wrong | Fix the code. |
| Test oracle is wrong | Fix the test, with proof of the correct oracle. |
| Behavior intentionally changed | Submit `sancai_change.py propose` with an EC. |
| Corpus/labels intentionally changed | Submit a `corpus_rebaseline` EC and a science audit. |
| Unknown | Block and escalate; do not update the expectation. |

`intent.change_policy` declares `protected_globs`, `max_changed_files`,
`expected_change_allowed`, `science_audit_above`, `baseline_id`, and
`require_rollback_plan`. G0 freezes EC drafts before running tests. G3 rejects
any live EC that differs from the frozen manifest. H3 accepts the new baseline.

Never use "test failed → update the expected value → pass" as a workflow.

## Evidence format

Every evidence record includes the legacy fields:

```json
{
  "schema_version": 1,
  "wo": "WO-001",
  "commands": [
    {
      "command": "python3 -m unittest discover -s tests -q",
      "exit_code": 0,
      "output_sha": "sha256:..."
    }
  ],
  "diff_sha": "sha256:...",
  "collected_at": "2026-01-01T00:00:00Z",
  "artifacts": ["..."]
}
```

Rules:

- `exit_code` is authoritative; stdout is supporting evidence.
- Normalize nondeterministic output (test duration, temp paths) before hashing.
- `diff_sha` covers the exact diff that was verified.
- Evidence is immutable after collection.
- `test_policy` adds `tests` and `coverage`; `change_policy` adds
  `changed_files`, `protected_changes`, `integrity_violations`,
  `expected_changes`, `expected_change_manifest_sha`, `regressions`, and
  `science_required`.
- New keys appear only when the corresponding policy exists; a legacy intent
  produces byte-identical evidence and `evidence_sha`.

## Verifier independence

- A fresh context per verification.
- Different session or context id from the executor.
- Read-only tools.
- No access to the executor's narrative.
- The verdict is written through the harness script, not by hand.

## H3 acceptance

Before accepting a run:

- [ ] All Work Orders are `verified`.
- [ ] G0-R integration evidence is fresh and passed when `integration_policy` is required.
- [ ] The gate result is `verified`.
- [ ] The frozen expected-change manifest still matches the evidence.
- [ ] The project ledger matches the closeout baseline (when one was recorded).
- [ ] No open escalation.
- [ ] No blocker or critical finding.
- [ ] Open findings have an explicit disposition: `defer`, `waive`, or `ack`.
- [ ] The acceptance card is bound to the run, the findings hash, and `closeout_sha`.
- [ ] The closeout plan is journaled; project TODOs and requirement statuses publish only after acceptance.
