---
name: sancai-loop
description: "Use when running the Agent-in-the-Loop (Sancai) flow: signing an Intent, creating Work Orders, dispatching an isolated executor, collecting harness-owned evidence, running G0/G3 gates, and handling the three escalation triggers. Triggers: Sancai, agent in the loop, intent contract, work order, harness evidence, Sancai run, three-layer loop."
---

# Sancai Harness

**Agent runs the loop. Human designs the loop. System decides when work is verified. Human decides when the outcome is accepted.**

## Three loops

```text
L3 Human    Intent: goal / non-goals / AC / risk policy / budget
                │
L2 Harness  Work Order · G0/G3 · Evidence · Escalation · Capability tokens
                │
L1 Code     isolated executor: plan → act → verify → repair
```

- **L3** owns intent. It does not read diffs; it sees summaries and risk.
- **L2** owns policy, dispatch, gates, and evidence. It never writes business code.
- **L1** owns code. It cannot write evidence, declare done, or run irreversible actions.

## Contracts

| Contract | Writer | Purpose |
|---|---|---|
| `intent.json` | Human | goal / AC / risk policy / budget / approval |
| `run.json` + work orders | Harness | state, claim, owned_files, reversible |
| `evidence/<wo>.json` | Harness | commands, exit codes, hashes, hidden checks |
| `verdicts/<wo>.json` | Verifier | independent pass/fail + findings |

## Commands

Humans only need one entrypoint and five subcommands:

```
/sancai start "<goal>"       H1: sign intent, then run the loop automatically
/sancai approve <ESC-ID>     H2: approve one irreversible action
/sancai accept               H3: accept the outcome
/sancai status               read-only
/sancai abandon "<reason>"   terminal: abandon with an audit record
```

`run` and `check` are **not** human commands. After H1, the PM agent
executes the loop automatically:

```text
init → intent card → interactive confirm → record-intent
      → transition executing
      → add-wo → claim → spawn sancai-executor
      → sancai_check_ac.py
      → spawn sancai-verifier (fresh context-id) → sancai_verdict.py
      → sancai_gate.py --apply
```

H1 default: ask `Start / Edit / Cancel` in the interactive UI, then record the
explicit choice with `sancai_state.py record-intent`. High-risk runs use the card
+ `sancai_decide.py sign`; the hook turns it into the host permission prompt, so
the human clicks Allow. `sancai_human.py` is only the T4/terminal fallback.
H2/H3 use the card + `sancai_decide.py approve|reject|accept`; no command copying.

Stop and ask the human only on: irreversible / out_of_scope / spec_ambiguous.

## Human touchpoints

Before every human decision, render the card; never narrate it yourself:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/sancai_card.py" current --run <run>
```

It shows the current layer (L3/L2/L1), stage, progress, trigger, what happened,
why the human is needed, impact, and numbered options. Output it verbatim and
parse the reply using the grammar in `/sancai`. The card is generated from
`graph.json`, not from the model's memory.

Human replies are explicit:

- H1 / H2 approve: `confirmed` / `approved` / `yes`.
- A bare `1`, `ok`, or `whatever` is **not** approval; for an irreversible action, ask for the word.
- H3 reject: record a concrete `--reason`; do not infer rejection from silence.
- H3 accept: `accepted` / `confirmed` / `yes`; a bare `ok` or `1` is not acceptance.

## Card binding contract (Phase 1)

Every actionable card is persisted by `sancai_card.py` and ends with:

```
Card  CARD-xxxxxxxxxxxx   Code  xxxxxxxx
Reply example: <verb> CARD-xxxxxxxxxxxx xxxxxxxx
```

The card is the human's decision object; the decision command must prove it saw
that exact card:

```text
sign    --card-id <CARD-ID> --card-code <CODE>
approve --card-id <CARD-ID> --card-code <CODE>
reject  --card-id <CARD-ID> --card-code <CODE>
accept  --card-id <CARD-ID> --card-code <CODE> --session-id <id>
        [--ack-findings] [--disposition defer:<WO-ID> | waive:<reason>]
```

Binding rules:

- The agent copies the pair from the rendered card verbatim. **It never invents,
  guesses, derives, or reuses a card code.** A hallucinated code fails.
- A card is single-use. A consumed card cannot be replayed; render a new card.
- The card payload is HMAC-signed (`sancai_cards.py`); editing `goal`, `evidence`,
  `wos`, gate results, or findings invalidates it. The decision command also
  checks the live state still matches the card payload.
- Cards have a dwell tier: `T0`/`T1` immediate, `T2` (default) 3s, `T3` 10s,
  `T4` 60s. "too fresh" means wait; do not retry in a tight loop to bypass it.
- Accept cards hash the verdict findings. Findings require `--ack-findings`;
  major findings also require exactly one `defer:<WO-ID>` or `waive:<reason>`;
  blocker/critical findings can never be accepted.
- Verify a card at any time with
  `sancai_card.py verify --run <run> --card-id <CARD-ID> --json`.

## Scripts

```
sancai_state.py      run / WO state, claim, progress, accept, abandon
sancai_check_ac.py   G0: run AC, write harness-owned evidence
sancai_capability.py tool capability table, fail-closed check, capability tokens
sancai_gate.py       combine G0 + G3, write gate verdict
sancai_verdict.py    verifier writes a structured verdict via Bash
sancai_escalate.py   structured escalation, dedupe, queue, approval record
sancai_decide.py     native decision entrypoint: sign / approve / reject / accept / mint
sancai_human.py      TTY-only T4/terminal fallback for sign / approve / reject / accept
sancai_hook.py       PreToolUse / PostToolUse / SubagentStop / Stop guards
sancai_graph.py      derive graph.json; fixed queries (position/next/attempts/metrics/timeline/show)
sancai_card.py       render cards; `status` renders a read-only progress card
sancai_cards.py      card payload signing, verification, single-use, dwell, findings hash
```

Progress updates are mandatory:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/sancai_state.py" progress \
  --wo <WO-ID> --status doing --item "implement rotation"
```

## Invariants

```text
1. Authority belongs to the layer, not the role.
2. Completion is decided by harness-collected evidence, not by narration.
3. Irreversible actions only leave through a human-approved capability.
4. Unlisted tools are denied (fail closed).
5. The plugin is not a sandbox; pair it with OS-level isolation.
6. No eval, no autonomy.
7. The graph is a read model; it explains state, it never authorizes.
8. H1/H3 are contract gates, not cryptographic proof of a human; high-risk repos set `SANCAI_REQUIRE_TTY_SIGN=1` and use the native-prompt sign/mint path (T4 may use `sancai_human.py`).
9. Human decisions consume a rendered card: no card id + code, no decision. The model never invents a code.
10. `sancai_decide.py` is the only agent-allowed decision path; the hook forces `permissionDecision: "ask"`. Direct `sign/approve/reject/accept/write` and `sancai_human.py` are agent-denied.
11. The status line and timeline are generated by scripts; the model never invents progress.
```

## Three escalation triggers

```text
① irreversible   delete / force-push / pay / deploy / change permission
② out_of_scope   outside owned_files / budget / permissions
③ spec_ambiguous conflicting or missing acceptance criteria
```

Everything else (style, naming, normal test failures, reversible refactors) is the executor's job.

## Layout

```
.sancai/runs/<run>/
├── L3-intent/
│   ├── intent.json
│   └── decisions/{cards,escalations}/
├── L2-harness/
│   ├── run.json
│   ├── progress.md
│   ├── gates/<wo>.json
│   ├── evidence/<wo>.json
│   ├── verdicts/<wo>.json
│   └── tokens/
├── L1-code/{attempts,scratch}/
└── audit/{events.jsonl,graph.json}
```

## Subagents (MVP)

```text
PM (main session) ──► sancai-executor (L1)   writes code
                  └─► sancai-verifier (L2/G3) reads evidence, judges
```

Only these two. Explorer/architect are added only when eval proves the need.

## Required reading

1. `${CLAUDE_PLUGIN_ROOT}/references/coding-standards.md`
2. `${CLAUDE_PLUGIN_ROOT}/references/git-workflow.md`
3. `${CLAUDE_PLUGIN_ROOT}/references/progress-updates.md`
4. `${CLAUDE_PLUGIN_ROOT}/references/capability-table.md`

## Classic mode

The existing N0–N6 `spec-team` flow remains available as the classic mode.
Sancai is the target mode; classic mode is the fallback for teams not ready to switch.

## MVP limitations (be explicit)

```text
- Single repo, single writer, serial. No multi-repo / A2A yet.
- The default Bash allowlist is conservative. Extend .sancai/capability-table.json
  per project; unlisted commands are denied (fail closed).
- Acceptance checks run in the repo root. Isolated per-Work-Order worktrees
  are a Phase 2 item.
- The Stop guard only applies when run.json has a recorded session id;
  otherwise it allows exit to avoid trapping the user.
- The plugin is not a sandbox. Use OS-level isolation for untrusted work.
- No trust ledger / SQLite / daemon / shadow review queue in MVP.
```
