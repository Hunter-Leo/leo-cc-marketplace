# Dead Ends

> Purpose: record attempts that have failed and should not be retried.
> **First thing after resuming a session: read this file.** New teammates must check this table before acting.
> Append only, never delete; failed attempts are evidence too (essence I-2).

| ID | What was tried | Why it failed | Evidence | Reason not to retry |
|---|---|---|---|---|
| DE-01 | <specific approach: file/command/parameters> | <root cause> | <command + output / file:line> | <under what conditions it still fails> |

## Usage rules

- Read this table before starting any unit; when a similar approach is hit, first record "checked DE-xx" in progress.md, then decide whether to change course.
- New entries must include evidence; "it feels wrong" is not accepted.
- For an entry that might work after conditions change, append `DE-xx-revisit` explaining the change; do not modify the original entry.
- When the same dead end is mistakenly retried a second time, annotate the corresponding progress row with `repeat: DE-xx`, so the PM can hold accountable and improve the launch prompt.
