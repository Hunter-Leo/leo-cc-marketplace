# Intent Alignment (Sancai H1)

> H1 is not a yes/no dialog. The run must first make the intent clear enough to
> test, then record how the human resolved every ambiguity. The alignment record
> is part of `intent.json`; changing it changes the intent snapshot and
> invalidates any card signed against the old snapshot.

## Flow

```text
draft intent.json
      │
      ▼
sancai_intent.py assess
      │
      ├─ aligned ──────────────► render intent card ─► H1 decision
      │
      └─ needs_alignment
             │
             ├─ questions ─► human answers in conversation
             ├─ glossary --write ─► CONTEXT.md
             ├─ adr --title ─► ADR-NNN
             │
             ▼
      sancai_intent.py record --status aligned --answers "..."
             │
             ▼
      render intent card ─► H1 decision
```

If the ambiguity cannot be resolved before execution, record `deferred` with a
reason. `deferred` is explicit debt, not silent approval; the reason is stored
and shown in the card payload.

## Clarity signals

`assess` is deterministic. It does not invent requirements; it detects:

| Signal | Condition | Question |
|---|---|---|
| `goal_short` | goal < 30 chars | What concrete outcome should be true? |
| `vague_term:<term>` | robust/scalable/better/… | Define the term as a measurable condition |
| `non_goals_missing` | `non_goals` empty | What is explicitly out of scope? |
| `acceptance_weak:<id>` | `expect` has no observable check | What check proves it passed? |
| `manual_ratio_high` | manual AC > 20% | Which criteria can be automated? |
| `owned_files_missing` | `owned_files` empty | Which files may change? |
| `open_question` | `open_questions` non-empty | Resolve or defer each question |

Exit code: `0` aligned, `2` needs alignment.

## Question bank

Ask one question at a time, in the human's language. Do not read the whole list
as a wall of text.

- Outcome: "What is true after this run that is not true now?"
- Boundary: "What must not change?"
- Evidence: "Which command or artifact proves this?"
- Failure: "What would make you reject the result?"
- Reversibility: "If this is wrong, how do we undo it?"
- Terms: "Define '<term>' so two engineers would agree."
- Trade-off: "If we cannot have both, which do we keep?"

If the human cannot answer, propose 2–3 concrete options with consequences and
ask them to choose. Do not invent an answer.

## Term grilling, glossary, ADR

- `sancai_intent.py glossary --run <run> --write` creates
  `L3-intent/CONTEXT.md` with candidate terms and an open/defined status.
- Fill definitions before recording alignment when a term changes behavior.
- `sancai_intent.py adr --run <run> --title "<decision>"` creates
  `L3-intent/decisions/adr/ADR-NNN-<slug>.md` for hard-to-reverse decisions.
- ADR status starts `Proposed`; H1 acceptance does not automatically make it
  `Accepted`. Record the human decision in the ADR when it is accepted.

## Alignment record

```json
{
  "alignment": {
    "schema_version": "sancai.intent-alignment.v1",
    "status": "aligned",
    "recorded_at": "2026-11-24T17:00:00+00:00",
    "session_id": "s1",
    "answers": "owner=payments; retry=3; metric=p95<300ms",
    "reason": "",
    "signals": ["vague_term:fast"],
    "questions": ["Define 'fast' as a measurable condition, or remove it."],
    "questions_sha": "..."
  }
}
```

`sign` and `record-intent` refuse when `alignment.status` is neither `aligned`
nor `deferred`. `intent_snapshot` includes the alignment block, so a card signed
before a later alignment edit is stale.

## H1 card

The intent card payload includes `alignment_status`. The card options remain
`Start / Edit / Cancel`:

- **Start** only after alignment is `aligned` or explicitly `deferred`.
- **Edit** returns to `assess`; do not record an approval.
- **Cancel** abandons the run.

## Anti-patterns

- Recording `aligned` with `--answers "ok"` and no resolution.
- Treating `deferred` as approval without a reason.
- Asking ten questions at once.
- Letting the agent answer its own alignment questions.
- Editing `intent.json` after the card is rendered without re-rendering it.
- Creating ADRs for reversible, local decisions.
