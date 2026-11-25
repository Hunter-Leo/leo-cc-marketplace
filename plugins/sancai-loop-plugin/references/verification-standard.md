# Verification Standard (Sancai)

> G0 decides whether the Work Order is ready for review. G3 decides whether it
> is verified. Neither step trusts narration; both trust evidence.

## G0 — executor gate

Before submitting a Work Order:

- [ ] Formatter and linter pass.
- [ ] All tests pass; no regression.
- [ ] New behavior has normal, edge, and error tests.
- [ ] Core logic coverage is at least 80%, or the gap is justified in `design.md`.
- [ ] Public APIs have type annotations and docstrings.
- [ ] No secret, token, or environment value is written to evidence.
- [ ] The diff stays inside `owned_files`.
- [ ] No test is skipped, weakened, or replaced by a stub.

G0 evidence is harness-owned. The executor may run checks; it may not write or
edit `evidence/` or `verdicts/`.

## G3 — independent verification

The verifier receives only:

- `L2-harness/evidence/<WO>.json`
- the acceptance criteria from `intent.json`
- the diff
- the relevant standards (`design-principles`, `data-model`, `comment`, `verification`)

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

## Evidence format

Every evidence record includes:

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

## Verifier independence

- A fresh context per verification.
- Different session or context id from the executor.
- Read-only tools.
- No access to the executor's narrative.
- The verdict is written through the harness script, not by hand.

## H3 acceptance

Before accepting a run:

- [ ] All Work Orders are `verified`.
- [ ] The gate result is `verified`.
- [ ] No open escalation.
- [ ] No blocker or critical finding.
- [ ] Open findings have an explicit disposition: `defer`, `waive`, or `ack`.
- [ ] The acceptance card is bound to the run and the findings hash.
