# Progress

> Purpose: a per-person timeline of observable actions, for the PM and resuming teammates to judge progress.
> **Append only, never rewrite.** If an old row is wrong, append a correction row with `corrects: <original time>` in Result; do not delete or edit the old row.
> One row = one observable action; times use a fixed timezone, consistent across the file.

## <owner-1>

| Time | Actor | Unit | Action | Result |
|---|---|---|---|---|
| <YYYY-MM-DD HH:MM> | <name> | <U-01> | <read upstream / start implementation / run tests / commit / report> | <PASS \| FAIL \| BLOCKED + one-line evidence> |

## <owner-2>

| Time | Actor | Unit | Action | Result |
|---|---|---|---|---|
| <YYYY-MM-DD HH:MM> | <name> | <U-02> | <action> | <result> |

## <owner-3>

| Time | Actor | Unit | Action | Result |
|---|---|---|---|---|
| <YYYY-MM-DD HH:MM> | <name> | <U-03> | <action> | <result> |

## Summary (maintained by PM, append-only)

| Round | Total units | PASS | FAIL | BLOCKED | Notes |
|---|---|---|---|---|---|
| <N> | <n> | <n> | <n> | <n> | <one line> |
