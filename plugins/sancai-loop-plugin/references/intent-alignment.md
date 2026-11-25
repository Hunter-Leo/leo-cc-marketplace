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
sancai_intent.py assess --json
      │
      ├─ aligned ──────────────► render intent card ─► H1 decision
      │
      └─ needs_alignment
             │
             ▼
      Agent reads project context:
        README / docs / git log / code+tests in owned_files
             │
             ▼
      per signal: draft 2-3 grounded candidates
        (concrete intent + consequence + one recommendation)
             │
             ├─ glossary --write ─► CONTEXT.md
             ├─ adr --title ─► ADR-NNN
             ▼
      AskUserQuestion, one signal at a time
        candidate 1 / 2 / 3 / Other = write your own
             │
             ▼
      write resolutions.json
        [{code, choice, source: proposed|user}]
             │
             ▼
      sancai_intent.py record --status aligned --resolutions ...
             │  (refused unless every signal is covered)
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

## Candidate protocol (agent proposes, human chooses)

The script surfaces signals; the agent turns each into a decision the human can
make in one click. For every signal:

1. **Read context first** — README/docs, recent `git log`, code and tests under
   `owned_files`, and project conventions. Every candidate must be grounded in
   something real in this repository.
2. **Offer 2-3 candidates**, each with:
   - the concrete intent (a testable condition, boundary, or file set)
   - the consequence or what it gives up
   - exactly one recommendation marker
3. **Ask one signal at a time** through `AskUserQuestion`. The built-in
   **Other** option is "I'll write my own"; never remove it or answer for the
   human.
4. **Persist the choice** with `source: proposed` (picked a candidate) or
   `source: user` (wrote their own) via `record --resolutions`.

Example for `vague_term:fast`:

```text
Q: Define "fast" for this run.
  1. p95 < 300ms on the checkout load test   [recommended]
     → measurable; requires the checkout load-test fixture
  2. first paint < 1s on the marketing page
     → narrower scope; does not cover checkout
  3. Other: write your own definition
```

If the repository has no evidence to ground a candidate, say so and ask an open
question instead of inventing options.

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
    "answers": "vague_term:fast=p95<300ms; non_goals_missing=do not change CLI flags",
    "reason": "",
    "signals": ["vague_term:fast", "non_goals_missing"],
    "questions": ["Define 'fast' as a measurable condition, or remove it."],
    "questions_sha": "...",
    "signals_sha": "...",
    "resolutions": [
      {"code": "vague_term:fast", "choice": "p95 < 300ms under the load test", "source": "proposed"},
      {"code": "non_goals_missing", "choice": "do not change CLI flags", "source": "user"}
    ]
  }
}
```

`sign` and `record-intent` refuse when `alignment.status` is neither `aligned`
nor `deferred`. `aligned` also refuses unless `resolutions` covers every
current signal. `intent_snapshot` includes the alignment block, so a card signed
before a later alignment edit is stale.

## H1 card

The intent card payload includes `alignment_status`. The card options remain
`Start / Edit / Cancel`:

- **Start** only after alignment is `aligned` or explicitly `deferred`.
- **Edit** returns to `assess`; do not record an approval.
- **Cancel** abandons the run.

## Anti-patterns

- Recording `aligned` with `--answers "ok"` and no resolution.
- Recording `aligned` without covering every signal (`record` now refuses).
- Offering generic candidates that ignore the repository.
- Offering candidates without consequences, or marking all of them recommended.
- Asking ten questions at once.
- Letting the agent answer its own alignment questions.
- Editing `intent.json` after the card is rendered without re-rendering it.
- Creating ADRs for reversible, local decisions.
