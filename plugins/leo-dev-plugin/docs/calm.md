# calm

Pause, reset, and analyze. Use when stuck on a bug, confused about what's happening, or when the agent is jumping to fixes too quickly.

## What It Does

The calm command forces a structured pause:

1. **Stops all forward motion** — no code changes, no proposals, no experiments
2. **Fills a root-cause table** — what was tried, what happened, why it didn't work
3. **Writes an analysis** — single root cause, 2-3 options with trade-offs, a recommendation
4. **Waits for explicit "continue"** — nothing happens without user approval

After "continue", the session stays in deliberate mode: one step at a time, wait for confirmation, no multiple-fix turns.

## When to Use

| Situation | Why |
|-----------|-----|
| A fix failed twice | Breaking the loop prevents compounding bad assumptions |
| You don't understand the error | The table forces you to articulate what you know |
| Agent is proposing too many things at once | calm reels it back to one step at a time |
| Context feels overwhelming | The structure reduces cognitive load |
| LLM "context anxiety" | Calm breaks the rush-to-fix cycle by requiring methodical analysis before action |

## Best Practices

### 1. Use early

Don't wait until you're deep in a hole. If something feels off or unclear, call `/calm` immediately. It costs a few seconds and can save hours.

### 2. Be specific in the table

```
| What was tried | Result | Why it didn't work |
|----------------|--------|-------------------|
| Increased timeout | Still timing out | Root cause is auth, not latency |
```

Hand-wavy entries defeat the purpose.

### 3. The recommendation is binding

After calm, you and the agent commit to the recommended approach. If it fails, call calm again.

### 4. Session mode persists

Once calm is activated, the session stays in deliberate mode until you say "unwind". This means every step requires your confirmation — no assumption of speed.

### 5. `continue` vs `unwind`

- **continue** — proceed with the approved plan, one step at a time
- **unwind** — exit deliberate mode, return to normal agent behavior

## Anti-Patterns

- **Skipping the table** — the table is the most important part. Don't let the agent skip it.
- **Multiple fixes in one turn** — if the agent tries this, call calm again.
- **Vague root causes** — "something is wrong" is not a root cause. Push for a specific technical statement.
