# Handoff

> Purpose: the **single recovery entry point** after teammate context is lost.
> Updated by the PM at the end of each round or before a session interruption. A missing fixed field makes the handoff invalid; on resume it is treated as invalid and regenerated.

## resumption_prompt (ready to paste)

```text
You are <role>, joining Round <N> of run <run>.
Repository: <repo absolute path>, branch: <branch>, HEAD: <sha>.
Read in order: <run>/handoff.md → <run>/team-plan.md → <run>/findings.md → <run>/dead-ends.md.
Your work unit: <U-xx>, owned_files: <paths>.
Do not redo: <do_not_redo summary>.
Next step: <next_action>.
On completion, report per rails R-10.
```

## State snapshot

| Field | Value |
|---|---|
| round | <N> |
| branch | <branch> |
| HEAD | <sha> |
| uncommitted | <none \| file list> |
| last passing test | <command> → <result> @ <YYYY-MM-DD HH:MM> |
| context_minimum | <minimal file set needed for recovery, in reading order, comma-separated> |

## Pending items

- **open issues**: <list of F-xx / Q-xx with severity; write "none" if none>
- **next_action**: <the next concrete thing to do, directly executable>
- **do_not_redo**: <items already done or ruled out, pointing to progress.md / dead-ends.md entries>
- **blocked_on**: <waiting on whom / what; write "none" if none>

## Staleness policy

| Field | Value |
|---|---|
| stale_threshold_days | <default 7> |
| stale_action | <when past threshold: re-run last passing test, verify HEAD and uncommitted; if either does not match, this file is void and must be regenerated> |
| last_verified_at | <YYYY-MM-DD HH:MM> |
