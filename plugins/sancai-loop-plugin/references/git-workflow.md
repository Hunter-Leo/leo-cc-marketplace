# Git Workflow (Sancai)

> Git is the durable history of verified work. One run, one branch; one verified
> Work Order, one commit; one accepted run, one merge and tag.

## Lifecycle

```text
H1 approved
  └─ git status --porcelain --untracked-files=no (must be empty)
       └─ git switch -c sancai/<run-id>
       │
       ├─ WO-001 G3 verified -> commit
       ├─ WO-002 G3 verified -> commit
       └─ WO-003 G3 verified -> commit
              │
              ▼
         H3 accepted
              └─ git merge --no-ff
                   ├─ tag sancai-<run-id>
                   └─ release vX.Y.Z
```

## Before the run branch

- `git status --porcelain --untracked-files=no` must be empty. Uncommitted
  tracked changes mean the run branch would inherit unrelated work and pollute
  `git diff HEAD` evidence. Untracked files are allowed: they never appear in
  `git diff HEAD` and are not staged unless named explicitly.
- If it is dirty, commit or stash the existing work on its own branch, or ask
  the human how to proceed. Do not carry unrelated changes into the run branch.
- H1 artifacts (`intent.json`, alignment, ADRs, cards, evidence, verdicts) stay
  in `.sancai/`, which is gitignored. Do not commit them.

## Branches

- Create one branch per run after H1 approval: `sancai/<run-id>`.
- Do not create a branch per Work Order; it fragments evidence and history.
- Do not commit to `main` or another run's branch.
- Parallel runs use separate branches and, when needed, separate worktrees.
- Do not delete a run branch unless the user explicitly asks.

Allowed types for the optional prefix: `feat`, `fix`, `refactor`, `test`,
`docs`, `style`, `perf`, `ci`, `build`, `chore`.

## When to commit

- Only after G3 returns `verified` for that Work Order.
- One Work Order, one commit. Do not batch multiple Work Orders.
- Do not commit unverified attempts; their evidence stays in `.sancai/`.
- Run the acceptance commands before committing.
- Do not commit `.sancai/` runtime artifacts, tokens, evidence, or verdicts.

## Commit message

```text
[<run-id>] <WO-ID> <type>: <Capitalized imperative summary, <= 72 chars>

Why this change is needed and what it enables. Wrap at 72 chars.

AC: AC-1, AC-2
Evidence: <evidence_sha>
Verdict: <verdict_sha>
Risk: low | medium | high
```

Example:

```text
[2026-11-24-card-binding] WO-002 feat: bind decisions to one-time cards

Human decisions must be tied to the rendered card so a stale or forged
approval cannot be replayed. This adds card id and code checks to the
sign, approve, reject, and accept paths.

AC: AC-1, AC-3
Evidence: 9fe90016351044de53bec82e0955bb83a98a7973539ff7b4893c3d32310bc885
Verdict: 3bd5fc3691362632014bbfe5c6e0ac6ec51104228894cfb7178f687ca36dc338
Risk: medium
```

Rules:

- Summary: imperative, capitalized, no trailing period, <= 72 characters.
- Body explains why and what, not how.
- Trailers are machine-readable and required for Sancai runs.
- Never rewrite published history; no force push.

## Pre-commit checklist

- [ ] All tests pass; no regression.
- [ ] Formatter and linter pass.
- [ ] No secrets or environment-specific values.
- [ ] Type annotations and docstrings are complete.
- [ ] Only this Work Order's `owned_files` are staged.
- [ ] The current branch is `sancai/<run-id>`.
- [ ] No `.pyc`, log, `.DS_Store`, or `.sancai/` artifact is staged.

## Merge

Merge only after H3 acceptance. Use `--no-ff` to preserve the run boundary:

```bash
git switch main
git merge --no-ff sancai/<run-id>
git tag sancai-<run-id>
```

Merge message:

```text
<type>(<scope>): <imperative summary>

## Summary
- ...

## Work Orders
| WO | Verdict | Evidence |
|---|---|---|
| WO-001 | pass | <sha> |

## Test Plan
- [ ] acceptance commands pass
- [ ] no regressions
- [ ] open findings dispositioned
```

## Versioning

Use semver: `MAJOR.MINOR.PATCH`, with an optional pre-release suffix
`-rc.N` for release candidates.

| Change | Version |
|---|---|
| Breaking change | `MAJOR` |
| New feature, backward compatible | `MINOR` |
| Bug fix, docs, refactor | `PATCH` |
| Release candidate | `X.Y.Z-rc.N` |
| Stable release | `X.Y.Z` |

Rules:

- `N` starts at `1` and increases for every candidate: `0.10.0-rc.1`,
  `0.10.0-rc.2`, then `0.10.0`.
- A candidate is cut from `main` only after tests, compileall, and plugin
  validation pass.
- `plugin.json`, `marketplace.json`, the tag, and the changelog entry must all
  carry the same version string.
- Do not mutate or re-tag a published candidate. Fix it with `rc.N+1`.
- Promote to the stable version only after H3 acceptance and a clean release
  check. The stable tag may point to the final candidate commit or to a new
  commit that only changes version metadata.
- Pre-release versions sort before the stable version in semver:
  `0.10.0-rc.2 < 0.10.0`.
- Do not mark a candidate as `latest`; keep it on a pre-release channel.

## Release

- Update `CHANGELOG.md` using Keep a Changelog; keep `[Unreleased]` and add
  `[X.Y.Z-rc.N]` or `[X.Y.Z]`.
- Bump `.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json` to the
  same version.
- Tag the release `vX.Y.Z[-rc.N]`; tag the run `sancai-<run-id>`.
- Release notes list run IDs, acceptance criteria, evidence hashes, verifier
  verdicts, and known limitations.
- Publish only from `main` with a clean worktree.
- Commit the version bump as `chore(release): X.Y.Z[-rc.N]`.

## Rollback

- One Work Order fails: revert that commit, or return it to `changes_requested`.
- The whole run is abandoned: `/sancai abandon`, keep the branch and audit chain,
  do not delete them.
- A bad merge: revert the merge commit; do not rewrite `main`.
- A released regression: patch forward with a new version; do not retag.
