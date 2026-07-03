# Phase B Agent Brief — Quick Reference for Execution Agents

> **Purpose:** This brief covers everything a sub-agent needs to execute tasks in spec-coding-skill Phase B. Read this first. Full documents are referenced when detailed context is needed.

## 1. Task Sizing

| Size | Criteria | Workflow |
|------|----------|----------|
| XS | 1 file, trivial | inline init.md → implement → test → commit |
| S | 1-3 files, well-defined | lightweight init.md → implement → test → commit |
| M | Multiple modules | Full Phase 01-07 flow |
| L/XL | Cross-requirement | Full flow + Blueprint layer + Phase 02 mandatory |

## 2. Method Selection (at EVERY phase entry)

1. Identify methods tagged for this phase (see [SKILL.md § Methods](../../SKILL.md#methods))
2. Read `## When to Use` / `## Do Not Use` from the method file in `references/methods/`
3. Evaluate triggers against current context
4. Apply if triggers match; produce factual justification if not. Generic "not needed" is invalid.

## 3. Self-Check (BEFORE marking task done)

- [ ] Reviewed plan.md and relevant docs before writing code
- [ ] Code follows Constitution in init.md
- [ ] New public functions/classes/files have complete docstrings
- [ ] Existing tests still pass (no regressions)
- [ ] New unit tests cover: normal, edge, error/exception cases
- [ ] All tests pass — do not proceed if any test fails
- [ ] No hardcoded secrets or environment-specific values
- [ ] No new linting errors

## 4. Execution Loop (12 steps, per task)

```
0.  Confirm feature branch (git branch --show-current)
1.  Mark task as in-progress in tasks.md
2.  Read plan.md + relevant docs
3.  Read affected source files (in sections if large)
4.  Read standards + Method Selection (TDD if clear public interface)
5.  Implement minimal change
6.  Verify code against SOLID/standards checklist
7.  Write tests (normal + edge + error)
8.  Run all tests — all must pass
9.  Update tasks.md: status=done, notes summary
10. Pre-commit check (tests, lint, secrets, docstrings, correct branch)
11. Commit (git add <files> && git commit)
12. If interactive: show summary, ask before next task
```

After step 11, repeat from step 0 for next task.

## 5. Deviation Protocol

| Severity | When | Action |
|----------|------|--------|
| **Low** | Rename, helper extraction, minor refactor | Continue. Note in commit. |
| **Medium** | Bug in unrelated code, small new tool | Log to issues.md. Continue. |
| **High** | Plan infeasible, interface must change | STOP. Log to issues.md. Set task blocked. Present options. |

**If unsure, treat as HIGH.**

### High Severity Templates

**plan-deviation:**
- Option A: Update plan.md, fix within current round
- Option B: Log issue, defer to Round N+1 (recommended)
- Option C: Rollback, restart with different approach

**discovered-bug:**
- Option A: Log to TODO.md, continue (recommended)
- Option B: Fix in current round

**scope-creep:**
- Option A: Add to current tasks.md (recommended)
- Option B: Log to issues.md, plan for Round N+1

**technical-contradiction:**
- Option A: Update plan + ADR documenting the resolution (recommended)
- Option B: Log issue to Round N+1 (when full re-design needed)
- Option C: Escalate to architecture review (when cross-module impact)

### Prohibited: Implicit Fallback

- No silent catch and return default
- No hidden retry masking transient failures
- No log-and-continue past real errors
- No silent fallback to less correct implementation

## 6. Quick Reference

### OOP/SOLID
- **SRP** — one reason to change per class/module
- **OCP** — open for extension, closed for modification (no if/elif chains)
- **LSP** — subtypes must be substitutable
- **ISP** — small focused interfaces
- **DIP** — depend on abstractions, not concretions

### Coding Standards (all languages)
- Type annotations on all function parameters and return values
- Docstrings: every file, class, public function (Args, Returns, Raises)
- Google Style for all comments/docstrings
- Comments explain *why*, not *what*
- DRY: no duplicated logic
- No hardcoded secrets — use env vars
- Validate all external inputs

### Git
- Branch: `<type>/[NNN]-[req-name]` (created at A→B Gate)
- Commit: `[NNN] T-XXX <type>: <imperative summary ≤ 72 chars>`
- Pre-commit: tests pass, no lint errors, no secrets, docstrings complete
- Types: `feat` · `fix` · `refactor` · `test` · `docs` · `style` · `perf` · `ci` · `build` · `chore`
- Never commit to main

### Integration Tests
- Do NOT mock internal code or external dependencies
- Mock only at system boundaries (network, time, randomness, third-party APIs unavailable in test env)
