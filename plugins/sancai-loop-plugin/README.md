# sancai-loop-plugin

Sancai Loop — an Agent-in-the-loop (AITL) harness for Claude Code.

**Agent runs the loop. Human designs the loop. System decides when work is verified. Human decides when the outcome is accepted.**

## Quick start

Before the first card or verifier token, export a secret outside the repository:

```bash
export SANCAI_SECRET="$(cat ~/.config/sancai/secret 2>/dev/null || openssl rand -hex 32)"
```

Cards and verifier tokens fail closed without it. Then humans only need one
entrypoint and five subcommands:

```bash
# 1. Sign an intent and run the loop automatically
/sancai start "Add refresh-token rotation to the auth service"

# 2. If an irreversible action is needed
/sancai approve ESC-001

# 3. Accept the outcome
/sancai accept

# Read-only status
/sancai status

# Abandon with an audit record
/sancai abandon "scope changed"
```

`run` and `check` are **not** human commands. After H1, the PM agent runs
add-wo → claim → executor → G0 → G3 → gate automatically, and stops only on
the three escalation triggers.

## End-to-end workflow

```text
PROJECT LEDGER (spans runs)
  capture (agent) ──► TODO-* ──► promote + accept (human) ──► REQ-*
                                                              │
                             select --run <run> --req REQ-… ─┘
                                        │
                                        ▼
H1  INTENT (run = planning)
  draft intent (goal / non-goals / AC / owned_files / budget)
    ├─ [optional] requirements select ──► requirements[] + revision+1
    ├─ assess ──► ambiguity signals
    ├─ agent reads repo context ──► 2-3 grounded candidates per signal
    │    (draws ASCII: material under review + option branches)
    ├─ AskUserQuestion, one question at a time (Other = free-form)
    ├─ record --resolutions (aligned) | --reason (deferred)
    ├─ card intent ──► human Start / Edit / Cancel ──► record-intent / sign
    ├─ clean tracked tree check
    └─ git switch -c sancai/<run>
                                        │
                                        ▼ transition --to executing
L2  WORK ORDER LOOP (run = executing)
  add-wo --req REQ-… ──► claim ──► sancai-executor
                                      │
                                      ▼
                              G0 sancai_check_ac.py
                              (harness runs AC, writes evidence)
                                      │
                                      ▼
                              sancai-verifier
                              (fresh context, read-only, independent)
                                      │
                                      ▼
                              sancai_verdict.py
                                      │
                                      ▼
                              G3 sancai_gate.py --apply
                                ├─ changes_requested ──► executor rework
                                ├─ blocked ──► H2 / human
                                └─ verified
  all WOs verified/merged ──► executing → reviewing

H2  ESCALATION (only three triggers)
  irreversible | out_of_scope | spec_ambiguous
    └─ open ──► card ──► human approve/reject
         └─ approve ──► one-time capability token ──► one scoped action
              (replay, expiry, or changed diff fails closed)

H3  ACCEPTANCE (run = reviewing)
  preflight: all WOs verified/merged · gates passed ·
             every selected REQ covered · no open escalation
    └─ accept card ──► human /sancai accept
         ├─ blocker/critical ──► refused
         ├─ major ──► defer:<WO-ID> (writes backlog TODO) | waive:<reason>
         └─ minor ──► --ack-findings
              └─ run = accepted

ABANDON
  planning | executing | reviewing ──► abandoned (reason recorded, audited)
```

## State machines

```text
Run
  planning ──► executing ──► reviewing ──► accepted
      │            │             │
      └────────────┴─────────────┴──────► abandoned

Work Order
  pending ──► in_progress ──► for_review ──► verified ──► merged
                  ▲               │
                  └── changes_requested
  blocked ◄──► in_progress          (blocked is cleared by a human)

TODO
  pending ──► promoted
     ├─────► deferred ──► promoted
     └─────► rejected

REQ
  proposed ──► accepted ──► (in_progress / verified: Phase 2)
      │           └──────► deferred / rejected
      └──────────────────► rejected
```

## Gates at a glance

| Point | Gate | Enforced by |
|---|---|---|
| H1 | ambiguity addressed, resolutions complete, intent signed, tracked tree clean | `sancai_intent.py`, `sancai_state.py sign`, `transition executing` |
| WO start | WO binds a selected `REQ-*`; claim recorded | `sancai_state.py add-wo/claim` |
| G0 | acceptance commands run by harness, evidence hashed | `sancai_check_ac.py` |
| G3 | verifier independent (context, prompt hash, read-only), evidence matches; science audit passes when required | `sancai_gate.py`, `sancai_verdict.py`, `sancai_science.py` |
| Reviewing | every WO verified or merged | `sancai_state.py transition` |
| H3 | all gates passed, requirements covered, findings dispositioned | `sancai_state.py accept` |

## Requirements across runs

Requirements live in a project ledger, not in a single run:

```
.sancai/project/requirements.json   accepted REQ-* with acceptance criteria
.sancai/project/backlog.json        raw TODO-* captures
.sancai/project/blueprint.md        generated view
```

A run's `intent.json` snapshots the accepted requirements it covers
(`requirements[]` + `revision`). Work Orders bind one with `add-wo --req`.
The agent may capture, list, and select; only the human may promote, accept,
defer, or reject. Unrelated discoveries are captured in the backlog and never
widen the current run. H3 acceptance refuses to finish until every selected
requirement has a verified Work Order, and `defer:<WO-ID>` captures a backlog
TODO instead of creating a Work Order in an already accepted run.

See `references/requirements-management.md` for the state machines.

## Loop budget

`intent.budget` has three fields only: `max_attempts`, `max_human_rounds`, and
`deadline_seconds`. Per-WO attempts, verifier retries, and no-progress Stop
leases derive from `max_attempts`. Exhaustion pauses the run; writes are
rejected, Stop is allowed, and a human can `sancai_decide.py budget-grant` or
abandon/accept.

## Science routing

Science roles are automatic, not a human checkbox. During H1 the PM runs
`sancai_science.py detect` and writes `intent.science`. Formula, paper,
dataset, statistical, numeric, simulation, and experiment signals set
`required=true`; uncertain detection also defaults to true. The PM then spawns
`sancai-researcher` and, for numeric claims, `sancai-science-auditor`. G3
requires a `pass` science audit for every WO when `required=true`.

## Human touchpoints

Before every human decision, render the card:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/sancai_card.py" current --run <run>
```

The card opens with an ASCII flow map of the three layers, with the current
decision marked `▶ … ◀`, then shows the stage, current layer (L3/L2/L1),
progress, trigger, what happened, why the human is needed, impact, and numbered
options. The flow map comes from `graph.json`; the model must output the card
verbatim. Before asking, the model also draws its own ASCII diagram of the
material under review (intent at H1, operation at H2, implementation and evidence
at H3); that diagram has no fixed format and must be grounded in the artifacts.

## Historical: Phase 1 card binding (v0.3.0)

The commands in this historical subsection are shown for the original CLI
contract. Current agent-facing decisions use `sancai_decide.py` and the native
permission prompt described above; direct `sancai_state.py sign/accept` and
`sancai_escalate.py approve/reject` are agent-denied.

Every actionable card is persisted under `.sancai/runs/<run>/L3-intent/decisions/cards/` and ends
with a binding footer:

```
Card  CARD-xxxxxxxxxxxx   Code  xxxxxxxx
Reply example: <verb> CARD-xxxxxxxxxxxx xxxxxxxx
```

Human decisions must be bound to that exact card:

```bash
sancai_state.py sign      --card-id CARD-... --card-code ...
sancai_escalate.py approve --card-id CARD-... --card-code ...
sancai_escalate.py reject  --card-id CARD-... --card-code ...
sancai_state.py accept    --card-id CARD-... --card-code ... --session-id ...
                        [--ack-findings] [--disposition defer:<WO-ID> | waive:<reason>]
```

Mechanisms:

- **Single-use card.** A consumed card cannot be replayed; each decision needs a
  freshly rendered card.
- **Signed payload.** `sancai_cards.py` HMAC-signs the payload (`SANCAI_SECRET` /
  `SANCAI_CARD_SECRET`); editing the goal, escalation evidence, WO states, gate
  results, or findings fails verification. If neither variable is set, card
  creation and verification fail closed.
- **Live-state binding.** `sign`/`approve`/`reject`/`accept` also check the
  current state still matches the card payload, so a stale card cannot approve
  a changed action.
- **Dwell tiers.** `T0`/`T1` immediate, `T2` (default) 3s, `T3` 10s, `T4` 60s.
  A too-fresh card is rejected with the remaining seconds.
- **Findings acknowledgement.** Accept refuses findings unless the human passes
  `--ack-findings`; major findings need exactly one `defer:<WO-ID>` or
  `waive:<reason>`; blocker/critical findings are never acceptable.
- **Verify.** `sancai_card.py verify --run <run> --card-id CARD-... --json`
  reports `verification.ok` and any problems.

The model never invents a card code. It copies the rendered footer; a missing,
wrong, tampered, stale, or already-used pair fails closed.

## Native human channel (v0.6.0)

- **H1 interactive by default.** The agent runs `sancai_intent.py assess --json`,
  then for each ambiguity signal reads project context and proposes 2-3 grounded
  candidate resolutions (with consequences and a recommendation) through the
  native question UI; the human picks one or writes their own. The agent records
  `--resolutions` (every signal must be covered) as `aligned`, or `deferred`
  with a reason, renders the intent card, asks `Start / Edit / Cancel` through
  the interactive question UI, and records the explicit choice with
  `record-intent`; the human does not copy card ids or run a command.
- **H2/H3 native permission prompt.** The agent calls
  `sancai_decide.py sign|approve|reject|accept`; the `PreToolUse` hook returns
  `permissionDecision: "ask"`, so Claude Code shows its normal Allow/Deny
  prompt. The human clicks, and the decision command records the session and
  the card pair. No terminal copy/paste is required. `sancai_human.py` remains the
  T4 / terminal-only path when a real TTY process is mandatory.
- **Mint uses the same prompt.** `sancai_decide.py mint` asks before minting a
  one-time token; the prompt shows the exact action and diff. `SANCAI_SECRET` is
  still required.
- **Decision latency.** Every decision stores `latency_seconds` on the intent
  approval, escalation record, and `outcome`, and appends it to
  `events.jsonl`.
- **Observability.** `sancai_graph.py metrics` now reports `decisions`,
  `median_latency_seconds`, `fatigue_suspected`, and `human_minutes` derived from
  decision latency.
- **Card rendering.** Approve / out-of-scope cards show the escalation's custom
  `options`; accept cards use `accepted` in the reply example.


## Observability (v0.8.0)

- **Status line.** A `UserPromptSubmit` hook injects one line
  (`Sancai <run> | <state> | <stage> | <progress> | next=<action>`). It is silent
  when idle, emits on state-fingerprint changes, and at most once every three
  turns when nothing changes. A stale terminal pointer is announced once.
- **Canonical JSON.** `sancai_state.py status --run <run> --json` returns one
  `SancaiStatus` object; `--run` works even when the active pointer is stale.
- **Timeline.** `sancai_graph.py timeline --run <run> --last 20` prints the
  append-only event history with actor, subject, and `from→to`.
- **Progress card.** `sancai_card.py status --run <run>` renders a read-only
  progress card with recent events; it never authorizes anything.
- **Self-healing active pointer.** `.sancai/active` is JSON; `accept`/`abandon`
  clear it, and a terminal run is no longer reported as active.
- **Structured next.** `sancai_graph.py next` adds `reason`, `check`, `allowed`,
  and `forbidden`; `init` refuses to overwrite a different non-terminal run
  unless `--takeover` is explicit.

## Physical layout (v0.10.0-rc.8)

**Sancai** (three powers: Heaven, Earth, and Human) means the runtime mirrors
that: `L3-intent` (human intent), `L2-harness` (execution control), and
`L1-code` (agent work). Each layer owns its own directory under
`.sancai/runs/<run>/`, so authority is visible in the filesystem rather than
inferred from a role name.

The plugin id is `sancai-loop-plugin`, the command is `/sancai`, and runtime
state lives under `.sancai/`.

## Three layers

```text
L3 Human    Intent: goal / non-goals / AC / risk policy / budget
                │
L2 Harness  Work Order · G0/G3 · Evidence · Escalation · Capability tokens
                │
L1 Code     isolated executor: plan → act → verify → repair
```

## State

```
.sancai/
├── project/
│   ├── requirements.json
│   ├── backlog.json
│   └── blueprint.md
└── runs/<run>/
    ├── L3-intent/
    │   ├── intent.json
    │   └── decisions/
    │       ├── cards/CARD-*.json
    │       └── escalations/ESC-*.json
    ├── L2-harness/
    │   ├── run.json
    │   ├── progress.md
    │   ├── gates/<wo>.json
    │   ├── evidence/<wo>.json
    │   ├── verdicts/<wo>.json
    │   └── tokens/*.json
    ├── L1-code/
    │   ├── attempts/
    │   └── scratch/
    └── audit/
        ├── events.jsonl
        └── graph.json
```

Local state is created with `0700` directories and `0600` files. `.sancai/` is
gitignored; never commit evidence, cards, tokens, or scratch.

## Invariants

1. Authority belongs to the layer, not the role.
2. Completion is decided by harness-collected evidence, not narration.
3. Irreversible actions only leave through a human-approved capability.
4. Unlisted tools are denied (fail closed).
5. The plugin is **not a sandbox**; pair it with OS-level isolation.
6. No eval, no autonomy.
7. The graph is a read model; it explains state, it never authorizes.
8. H1/H3 are contract gates, not cryptographic proof of a human; high-risk
   repos set `SANCAI_REQUIRE_TTY_SIGN=1` and use the native-prompt sign/mint
   path (T4 may use `sancai_human.py`).
9. H2/H3 human decisions consume a rendered card: no card id + code, no
   decision. H1's interactive `record-intent` is a contract gate, not a card.
10. `sancai_decide.py` is the agent-allowed path for H2/H3 and high-risk H1; the
    hook forces `permissionDecision: "ask"`. Direct `sign/approve/reject/accept/
    abandon/prepare/write` and `sancai_human.py` are agent-denied; H1's default
    `record-intent` records the native question UI's answer.
11. The status line and timeline are generated by scripts; the model never
    invents progress.
12. A raw capture never mutates an intent. Only `select` writes
    `requirements[]`, only in planning, and only with human-accepted REQs.

## Fool-proofing (v0.2.2)

A 13-scenario adversarial audit found 7 P0 issues; all have a mechanism now:

| P0 | Mechanism |
|---|---|
| Bash prefix bypass | `shlex` parsing, metacharacter rejection, argv-level allowlist, git index checks |
| agent self-mints token | `sancai_capability.py mint` is denied to the executor; only `sancai_decide.py mint` is allowed, and the hook forces the native permission prompt; `SANCAI_SECRET` is required |
| token reuse | token is renamed `.used` on first use; reuse is detected |
| state machine trusts caller | `sign` snapshot; `executing` needs signed intent; `reviewing` needs all WOs verified |
| verifier independence self-reported | `--context-id` must differ from executor/claim; prompt hash, read-only, evidence hash checked |
| findings do not block | pass + blocker/critical is rejected; gate and accept both check |
| H1 is prompt-only | `sign` records session, phrase, snapshot, nonce; execution cannot start unsigned |

Residual trust boundaries (read this before relying on it):

- This is **not a sandbox**. Bash policy is best-effort; build/test scripts can execute arbitrary repo code.
- H1 is a UX/contract gate, not cryptographic proof that a human approved. High-risk repos should set `SANCAI_REQUIRE_TTY_SIGN=1` and use `sancai_human.py sign` in a terminal; irreversible actions require the native-prompt `mint` path.
- Verifier independence is self-asserted context, not process attestation.
- `SANCAI_SECRET` in the environment is readable by same-user processes; use a secret manager in production.
- The threat model is mistakes and agent overreach by the same user, not a compromised same-user process or a malicious MCP server.

### Human-side fool-proofing

What exists:

- Every human touchpoint shows the three-layer position (L3/L2/L1), trigger, what happened, why you are needed, impact, and numbered options; the model adds an ASCII diagram of the exact material being confirmed (intent, operation, or implementation evidence).
- One decision at a time; queue numbers; the human does not memorize `ESC-*` ids.
- H1/H3 require explicit phrases. A bare `1`, `ok`, or `whatever` is not approval; `reject` requires a concrete reason.
- Irreversible actions cannot be batch-approved. The human approves a one-time token through the native prompt, bound to the exact action, diff hash, and TTL; a changed diff invalidates it.
- H1 `sign` binds the intent snapshot; an altered or stale intent cannot start execution.
- H3 `accept` refuses open escalations, unverified gates, missing verdicts, and blocker/critical findings.
- Every decision consumes a single-use card bound to a signed payload; a stale or tampered card fails.

What is not solved:

- Approval fatigue and rubber-stamping; dwell tiers slow the first 3s but do not add a second approver.
- Card display authenticity: the agent renders the card, so a compromised agent could show a fake one (the id/code binding prevents approving a different card, not faking the text).
- No cooling-off period for irreversible actions beyond the card dwell tier; `SANCAI_REQUIRE_TTY_SIGN=1` is optional.
- Human identity is not cryptographically proven.

For high-risk repos: enable `SANCAI_REQUIRE_TTY_SIGN=1`, run `mint`/`sign` in a human terminal, review the raw diff, and pair with OS-level isolation.

## MVP scope

- Single repository, single writer, serial.
- **No worktree.** The plugin runs in the current working tree; `git worktree` is only used by the separate `evals/` harness for isolated evaluation runs.
- No trust ledger, SQLite, daemon, shadow review queue, or parallel Router/Worker.
- Subagents: `sancai-executor` (L1), `sancai-verifier` (L2/G3), conditional H1
  `sancai-explorer` / `sancai-design-critic`, and conditional
  `sancai-researcher` / `sancai-science-auditor`.

## Scripts

| Script | Purpose |
|---|---|
| `sancai_paths.py` | shared `.sancai/` path layout |
| `sancai_state.py` | run / work-order state, claim, progress, accept, abandon |
| `sancai_requirements.py` | project `REQ-*` / `TODO-*` ledger, selection, blueprint |
| `sancai_intent.py` | H1 intent assessment, ambiguity signals, alignment record |
| `sancai_check_ac.py` | G0: run acceptance checks, write harness-owned evidence |
| `sancai_capability.py` | tool capability table, fail-closed check, capability tokens |
| `sancai_control.py` | three-parameter budget, progress fingerprint, pause/grant state |
| `sancai_science.py` | automatic science routing, audit check/record |
| `sancai_gate.py` | combine G0 + G3, write the gate verdict |
| `sancai_verdict.py` | verifier writes a structured verdict via Bash |
| `sancai_escalate.py` | structured escalation, dedupe, queue, approval record |
| `sancai_hook.py` | PreToolUse / PostToolUse / SubagentStop / Stop guards |
| `sancai_graph.py` | derive/query the process graph (read model) |
| `sancai_card.py` | render persistent human interaction cards from the graph |
| `sancai_cards.py` | card payload signing, verification, single-use, dwell, findings hash |
| `sancai_decide.py` | native decision entrypoint: sign / approve / reject / accept / mint; hook turns it into the host permission prompt |
| `sancai_human.py` | TTY-only T4/terminal fallback for sign / approve / reject / accept |

## Standards and versioning

The executor reads the standards in `skills/sancai-loop/SKILL.md`; the full
reference set lives in `references/`:

- `intent-alignment.md` — H1 ambiguity signals, questions, glossary, ADR
- `requirements-management.md` — project ledger, REQ/TODO states, capture points
- `design-principles.md` — AITL/OOP/SOLID and proportionality
- `coding-standards.md` — universal and language-specific rules
- `comment-standard.md` — docstrings, inline comments, TODO
- `data-model-standard.md` — schemas, IDs, validation, migration
- `documentation-standard.md` — durable docs and size matrix
- `verification-standard.md` — G0/G3 and evidence
- `execution-discipline.md` — read-before-write and WO scope
- `git-workflow.md` — branches, commits, merge, versioning
- `progress-updates.md` — progress protocol
- `capability-table.md` — tool capability policy
- `method-playbooks.md` — trigger-gated methods

Versions follow semver. Release candidates use `X.Y.Z-rc.N` (for example
`0.10.0-rc.8`); `plugin.json`, `marketplace.json`, the tag, and the changelog
must match. Promote to `X.Y.Z` only after H3 acceptance. See
`references/git-workflow.md`.

## Tests

```bash
python3 -m unittest discover -s plugins/sancai-loop-plugin/tests -v
python3 plugins/sancai-loop-plugin/tests/pokayoke_audit.py   # 13 adversarial scenarios
```

### Behavior evals

The unit tests above are deterministic and free. The behavior suite drives a
real Claude session and is billed to your account.

```bash
cd plugins/sancai-loop-plugin
./evals/run.sh --runs 1        # smoke: 5 cases, threshold 0.8
```

It covers intent clarification, no edits before H1, no completion without
G0/G3 evidence, verifier independence, and the H3 findings gate. See
`evals/README.md` for the case list, model pinning, and CI options.
