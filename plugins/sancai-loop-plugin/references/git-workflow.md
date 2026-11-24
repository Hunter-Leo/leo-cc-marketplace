# Git Workflow (Sancai)

> Git messages are English. Branch, commit, and merge rules apply to every executor.

## Branches

One branch per run, created before any code is written:

- M+: `<type>/<run>`, for example `feat/001-auth-refresh`
- XS/S: `<type>/<short-description>`

Type: `feat` / `fix` / `refactor` / `test` / `docs` / `style` / `perf` / `ci` / `build` / `chore`.

Forbidden: committing to `main`, committing to another run's branch, deleting a branch (unless the user explicitly asks).

## Commits

Format:

```text
[Sancai] <WO-ID> <type>: <Capitalized imperative summary, <= 72 chars>

<blank line>
Why this change is needed, and what it enables. Wrap at 72 chars.
```

Example:

```text
[Sancai] WO-001 feat: add refresh token rotation

The login flow needs one-time refresh tokens. This commit adds
rotation with reuse detection and persists only token hashes.
```

Rules:

- One logical commit per Work Order; do not mix Work Orders.
- Summary line <= 72 characters, imperative, no trailing period.
- The body explains why and what, not how.
- Run the acceptance commands before committing.
- Do not commit evidence, verdicts, tokens, or scratch under `.sancai/`.
- Do not `git push` or merge to the main branch; those are irreversible actions and go through `/sancai approve`.

## Merge

Performed by a human or an explicitly authorized role. Merge message:

```text
<type>(<scope>): <imperative summary>

## Summary
- ...

## Work Orders
| WO | Summary |
|---|---|
| WO-001 | ... |

## Test Plan
- [ ] acceptance commands pass
- [ ] no regressions
```

## Pre-commit checklist

- [ ] All tests pass
- [ ] No lint errors
- [ ] No secrets
- [ ] Type annotations / docstrings complete
- [ ] Only this Work Order's files staged
- [ ] Correct branch (`git branch --show-current`)

## Rollback

- One Work Order fails: revert that commit, or return it to `changes_requested`.
- The whole run is abandoned: `/sancai abandon`, keep the branch and audit chain, do not delete them.
