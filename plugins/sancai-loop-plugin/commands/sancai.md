---
description: "Sancai entrypoint. Humans only need five subcommands: start / approve / accept / status / abandon. Run and check are executed automatically by the harness."
argument-hint: "start <goal> | approve <escalation> | accept | status | abandon <reason>"
---

# /sancai

You are the Sancai entrypoint. Before acting, load
`${CLAUDE_PLUGIN_ROOT}/skills/sancai-loop/SKILL.md`.

`SANCAI_SECRET` (or `SANCAI_CARD_SECRET`) must be exported outside the
repository before any card or verifier token; without it the card/token steps
fail closed.

## Route

Parse `$ARGUMENTS`. The first token is the subcommand:

```
start <goal>        H1: draft + confirm intent, then run the loop automatically
approve <ESC-ID>    H2: approve one irreversible action
accept              H3: accept the outcome
status              read-only status
abandon <reason>    terminal: abandon with an audit record
```

If `$ARGUMENTS` is empty, infer from state:

```
no .sancai/active                     → start
active run + open escalation        → show it, ask to approve
active run, state=reviewing         → show summary, ask to accept
active run, state=executing         → status + next action
active run, state=accepted/abandoned→ status
```

**Do not ask the human to type `run` or `check`.** Those are internal.

When a run is active, render the card first:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/sancai_card.py" current --run <run>
```

It auto-detects intent / approve / out-of-scope / ambiguous / accept / blocked,
and prints "No action needed from you" when no human action is needed.

Every card opens with an ASCII flow map of the three layers. The current
decision is marked `▶ … ◀`, so the human sees both the upstream steps already
done and the downstream steps still ahead. Render the card verbatim; do not
redraw or paraphrase the map.

Every actionable card carries a **card binding**:

```
Card  CARD-xxxxxxxxxxxx   Code  xxxxxxxx
```

The human must echo that pair back. Pass it to the decision command as
`--card-id <CARD-ID> --card-code <CODE>`. The agent **never invents, guesses,
or reuses** a card code: it copies the rendered pair verbatim, and the harness
rejects a missing, wrong, tampered, or already-used card. Cards have a dwell
tier (`--tier`, default T2 = 3s); after 3s the code is accepted, before that it
is rejected as "too fresh". Do not retry in a loop to defeat the dwell.

---

## Project requirements (before H1)

Requirements outlive a run. The project ledger is:

```
.sancai/project/requirements.json   REQ-* accepted, testable requirements
.sancai/project/backlog.json        TODO-* raw captures
.sancai/project/blueprint.md        generated view
```

At H1, a run selects the `accepted` requirements it will cover. Selection writes
`requirements[]` and bumps `revision` in `intent.json`; it is allowed only while
the run is `planning` and the intent is unsigned.

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/sancai_requirements.py" init
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/sancai_requirements.py" list --status pending
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/sancai_requirements.py" status --json

# Only after `sancai_state.py init` in step 2:
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/sancai_requirements.py" select \
  --run <run> --req REQ-001
```

`list` shows backlog TODOs; `status --json` shows accepted REQs. If the project
has no accepted REQ yet, capture a TODO and ask the human to `promote` and
`accept` it before `select`.

Rules:

- Select only when an `accepted` REQ already covers the goal.
- If no REQ covers it, capture a TODO and ask the human to `promote` and
  `accept` it. **Never** promote or accept on the human's behalf.
- If the project has no ledger, a legacy intent without `requirements` is fine.
- An unrelated discovery is captured with `--relation unrelated`; it never
  mutates the current intent.

Read `${CLAUDE_PLUGIN_ROOT}/references/requirements-management.md` for the state
machines and capture points.

---

## start (H1 + automatic loop)

### 0. H1 research routing

The PM must know the full flow. Subagents need only
`references/agent-onboarding.md`, their role card, the upstream artifacts, and
role-specific references — do not make them read the whole SKILL.

Spawn only when the trigger applies:

| Trigger | Agent |
|---|---|
| unfamiliar module, cross-module, large repo, unknown callers/reuse/conflicts | `sancai-explorer` |
| two or more technical routes, algorithm/data-model/API choice, new module boundary | `sancai-design-critic` |
| ambiguous AC, missing non-goals, high-risk/irreversible work | `sancai-design-critic` with `intent-review` mode |
| formula/numeric/statistical/external evidence | `sancai-researcher` / `sancai-science-auditor` (automatic detection below) |
| small, clear, single-module task | no spawn; PM reads directly |

Explorer runs before the PM finalizes the draft. Design-critic runs after the
draft (and after `inspect.md` when it exists). At most three H1 research agents;
no recursive spawn.

Each spawn prompt must include:

```text
Role:        sancai-explorer | sancai-design-critic
Stage:       H1 / pre-intent | post-draft
Run:         <run>
Inputs:      <upstream artifact paths>
Lane:        read-only code; write <research artifact>
Output:      verdict + artifact paths
Stop:        BLOCKED if upstream is missing
Must read:   references/agent-onboarding.md + role-specific refs
```

Write returned artifacts into `L3-intent/research/` and record their paths in
`intent.research_refs`. Do not let a research agent write code or intent.

### 1. Draft the intent

Create `.sancai/runs/<run>/L3-intent/intent.json`:

```json
{
  "id": "INT-001",
  "version": 1,
  "goal": "one sentence that can determine success/failure",
  "non_goals": ["..."],
  "acceptance": [
    {"id": "AC-1", "check": "command", "run": "npm test -- auth", "expect": "exit_code == 0"}
  ],
  "manual_ac_ratio": 0.0,
  "risk_policy_ref": "policy/risk@1",
  "budget": {"max_attempts": 10, "max_human_rounds": 6, "deadline_seconds": 172800}
}
```

Do not hand-write `requirements` here unless the project ledger already contains
those accepted REQs. A new project has no `REQ-001`; `init` rejects unknown
requirements. Initialize the run first, then use
`sancai_requirements.py select` in step 2 to snapshot accepted requirements.

`budget` has only three fields: `max_attempts`, `max_human_rounds`, and
`deadline_seconds`. When a limit is exhausted the run becomes `paused`; only
`accept`, `abandon`, and a human-approved `sancai_decide.py budget-grant` remain
available. Per-WO/verifier/no-progress limits are derived from `max_attempts`.

### 1.1 Science routing (automatic)

Do not ask the human whether to use science agents. Run the detector after the
intent draft:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/sancai_science.py" detect \
  --intent .sancai/runs/<run>/L3-intent/intent.json --json
```

Write the result into `intent.science` with `required`, `signals`, `reasons`,
`agents`, and `confidence`. If `required=true`, spawn `sancai-researcher` before
asking the human about the intent; if numeric/statistical claims exist, also
spawn `sancai-science-auditor`. Uncertain detection defaults to `required=true`.
The human still signs the final intent and may reject the science decision, but
is not asked to choose the role.

Validate:

- every AC has an executable `run` and a concrete `expect`
- manual AC is forbidden by default; exceptions need a written reason and total ≤ 20%
- reject vague criteria

### 1.2 Design and intent review

After the draft, if it has multiple viable routes, an algorithm/data-model
choice, a new module boundary, or ambiguous AC, spawn `sancai-design-critic`
using the spawn packet above. For ambiguous AC/high-risk work, ask for
`intent-review` mode. Add the returned paths to `intent.research_refs`; the PM
still decides what goes into the intent. Do not ask the human whether to use
these agents.

### 2. Initialize (state=planning)

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/sancai_state.py" init \
  --run <run> --intent .sancai/runs/<run>/L3-intent/intent.json --session-id "${CLAUDE_CODE_SESSION_ID:-}"
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/sancai_state.py" activate --run <run>
```

Select the accepted requirements this run covers (optional but all-or-nothing:
once `requirements` is present, every Work Order must bind one):

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/sancai_requirements.py" select \
  --run <run> --req REQ-001
```

Work Orders then use `add-wo --req REQ-001`. A Work Order without `--req` is
refused when the intent has a requirements snapshot.

### 3. Align the intent (interactive)

Run the deterministic assessment first:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/sancai_intent.py" assess --run <run> --json
```

If it reports `needs_alignment`, resolve each signal with the human, one at a
time:

1. **Gather project context before proposing anything.** Read the repository
   README/docs, recent `git log`, the code and tests under `owned_files`, and
   the project's existing conventions. Candidate options must be grounded in
   this repository, not generic advice.
2. **Draft 2-3 candidate resolutions per signal.** Each candidate states the
   concrete intent, its consequence or trade-off, and which one you recommend
   and why.
3. **Ask through Claude Code's native interactive question UI**
   (`AskUserQuestion`): one signal per question, options = the candidates, and
   the built-in **Other** option is the human's "write my own answer" path.
   Prefix each question with the card's three-line ASCII flow map (`L3` / `L2` /
   `L1`, with `▶ … ◀` on the current step), then add your own ASCII diagram of
   the material the human is checking: for intent, goal, non-goals, acceptance,
   scope and the consequence of each choice; for an escalation, the operation,
   its target and its irreversible effect. Ground the diagram in
   `L3-intent/intent.json`, the card, and repository evidence — not memory. The
   shape is yours to choose; the requirement is that the human can see what they
   are confirming without opening files. Do not dump all questions at once. Do
   not answer for the human.
4. **Write the choices to a JSON array:**

```json
[
  {"code": "vague_term:fast", "choice": "p95 < 300ms under the load test", "source": "proposed"},
  {"code": "non_goals_missing", "choice": "do not change CLI flags", "source": "user"}
]
```

`source` is `proposed` when the human picked a candidate and `user` when they
wrote their own answer.

5. **Record the alignment:**

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/sancai_intent.py" record \
  --run <run> --status aligned --session-id "${CLAUDE_CODE_SESSION_ID:-}" \
  --resolutions <path|->          # JSON file, inline JSON, or - for stdin
```

`aligned` is refused unless the array covers every current signal. `--answers`
remains an optional summary and is derived from the resolutions when omitted.

If the ambiguity cannot be resolved before execution, record explicit debt
instead:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/sancai_intent.py" record \
  --run <run> --status deferred --session-id "${CLAUDE_CODE_SESSION_ID:-}" \
  --reason "<why this can wait>"
```

Optional term work:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/sancai_intent.py" glossary --run <run> --write
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/sancai_intent.py" adr --run <run> --title "<decision>"
```

`record-intent` and `sign` refuse without an alignment record.

**Anti-patterns:** asking ten open questions in one message, presenting options
that ignore the repository, letting the agent answer its own questions, or
recording `aligned` with choices that do not cover every signal.

### 4. Render the intent card and confirm (human gate H1)

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/sancai_card.py" intent --run <run>
```

Card creation requires `SANCAI_SECRET` or `SANCAI_CARD_SECRET`; without one,
`sancai_card.py` fails closed instead of issuing an unsigned card.

The card lists each acceptance command and its expected result. Those commands
are what G0 will execute with a shell; the human is approving the exact commands
shown, not just a count.

Present the card, then use the interactive question UI (Start / Edit / Cancel).
This is the default H1 path: the human does not copy card ids or run a command.

- If the human chooses **Start**, call the agent-allowed recorder with the
  human's exact choice:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/sancai_state.py" record-intent \
  --run <run> --session-id "${CLAUDE_CODE_SESSION_ID:-}" --message "confirmed"
```

- If the human chooses **Edit** or **Cancel**, update the intent or stop; do not
  record an approval.

H1 is a contract gate, not proof of an irreversible action. For high-risk runs
(`T3`/`T4`, or `SANCAI_REQUIRE_TTY_SIGN=1`), use the native decision entrypoint;
the PreToolUse hook turns it into Claude Code's permission prompt, so the human
clicks Allow instead of copying a command:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/sancai_decide.py" sign \
  --run <run> --session-id "${CLAUDE_CODE_SESSION_ID:-}" --message "confirmed" \
  --card-id <CARD-ID> --card-code <CODE>
```

`sancai_human.py sign` remains the T4/terminal-only path when the repository
requires a real TTY process.

### 5. Run the loop automatically

After H1 approval, verify the working tree is clean, then create the run branch
once:

```bash
git status --porcelain --untracked-files=no   # must print nothing
git switch -c "sancai/<run>"
```

If it prints anything, stop: commit or stash the existing tracked work on its
own branch, or ask the human how to proceed. Never carry unrelated changes into
the run branch. The intent and alignment artifacts stay in `.sancai/`
(gitignored) and are not committed.

Then run the loop without asking the human to type commands:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/sancai_state.py" transition --to executing
# If step 2 selected requirements, every Work Order must bind one:
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/sancai_state.py" add-wo --id WO-001 \
  --files "<exact paths>" --req REQ-001 --reversible true
# Legacy intent without requirements: omit --req.
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/sancai_state.py" claim --wo WO-001 --by executor
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/sancai_state.py" progress \
  --wo WO-001 --status doing --item "executor dispatched"
```

Then spawn **`sancai-executor`** with:

- the Work Order id and `owned_files`
- the acceptance criteria excerpt
- `${CLAUDE_PLUGIN_ROOT}/references/design-principles.md`
- `${CLAUDE_PLUGIN_ROOT}/references/coding-standards.md`
- `${CLAUDE_PLUGIN_ROOT}/references/comment-standard.md`
- `${CLAUDE_PLUGIN_ROOT}/references/data-model-standard.md`
- `${CLAUDE_PLUGIN_ROOT}/references/verification-standard.md`
- `${CLAUDE_PLUGIN_ROOT}/references/execution-discipline.md`
- `${CLAUDE_PLUGIN_ROOT}/references/git-workflow.md`
- `${CLAUDE_PLUGIN_ROOT}/references/progress-updates.md`

After the executor reports:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/sancai_check_ac.py" --run <run> --wo WO-001
```

Before spawning the verifier, prepare a one-time token bound to this Work Order's
current evidence. This is a human-approved native prompt:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/sancai_decide.py" verifier-prepare \
  --run <run> --wo <WO-ID>
```

Pass the printed `<token-id>:<secret>` pair to the verifier; it must use it as
`--verifier-token` when writing the verdict. The file stores only a hash, so
reading the token directory does not reveal the secret. Without a token,
`write` fails closed.

Then spawn **`sancai-verifier`** with the raw evidence + AC + diff (never the executor's narrative). The verifier writes its verdict through `sancai_verdict.py` with a fresh `--context-id` (different from the executor and its claim) and a `--prompt-hash`; a pass verdict carrying a blocker/critical finding is rejected.

If `intent.science.required` is true, spawn `sancai-science-auditor` as well and
record its audit through `sancai_science.py record-audit`. The gate requires a
`pass` audit for every Work Order; `fail` sends the WO back, and
`unverifiable`/missing blocks it.

Then:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/sancai_gate.py" --run <run> --wo WO-001 --apply
```

### 5. Stop only on the three triggers

Ask the human only when:

1. **irreversible** — delete, force-push, pay, deploy, change permission
2. **out_of_scope** — outside `owned_files`, new dependency, production access
3. **spec_ambiguous** — AC conflict or missing definition

Everything else (style, naming, normal test failures, reversible refactors) is the executor's job.

If an escalation reveals work that should not enter this run, capture it in the
project backlog instead of widening scope:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/sancai_requirements.py" capture \
  --title "<discovery>" --type finding --priority P2 \
  --source "run:<run>/WO:<wo>" --relation unrelated
```

Continue the run. A related capture may later be promoted by the human; an
unrelated one stays in the backlog.

### 6. Report

When the run reaches `reviewing`, report:

- Work Orders and gate results
- Requirement coverage (`REQ-*` → verified WOs)
- backlog items captured during the run
- evidence paths
- open findings
- ask for `/sancai accept`

---

## approve (H2)

1. Render the approval card; do not narrate it yourself:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/sancai_card.py" approve --run <run> --esc <ESC-ID>
```

The card's flow map marks `H2 approve`; keep that map visible when showing the
raw operation below. Before asking, add your own ASCII diagram of the decision:
operation → target → affected surface / diff → irreversible effect → options and
their consequences. Ground every node in the escalation payload or the diff, and
choose the shape that makes the trade-off legible.

2. Show the **raw operation**: exact action, arguments, target, diff hash, why it is irreversible, what cannot be undone.
3. Require an explicit confirmation word (`confirmed` / `approved` / `yes`) in
   the human's reply. The agent reads the card id/code from the rendered card
   and passes them; the human does not type or copy the pair. A bare number
   (`1`) or `ok` is **not** approval for an irreversible action.
4. Mark the escalation approved with the rendered card. Call the native
decision entrypoint; the hook returns `permissionDecision: "ask"`, so Claude
Code shows its permission prompt. The human clicks Allow; they do **not** copy
a command:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/sancai_decide.py" approve \
  --run <run> --id <ESC-ID> --message "<verbatim>" \
  --session-id "${CLAUDE_CODE_SESSION_ID:-}" \
  --card-id <CARD-ID> --card-code <CODE>
```

If the human rejects, record the reason instead (same card binding and native
prompt):

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/sancai_decide.py" reject \
  --run <run> --id <ESC-ID> --reason "<verbatim>" \
  --session-id "${CLAUDE_CODE_SESSION_ID:-}" \
  --card-id <CARD-ID> --card-code <CODE>
```

A rejection needs a concrete reason; silence or a bare `no` is not enough.
Never reuse an approval card for another escalation or another round.

5. Mint a one-time token. This also goes through the native prompt; the human
sees the exact action and diff before clicking Allow:

```bash
SANCAI_SECRET="<from keychain/env, never from the repo>" \
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/sancai_decide.py" mint \
  --run <run> --action "<action>" --diff-sha "<sha>" --ttl 600
```

6. Hand the token to the privileged executor. The agent cannot call
`sancai_capability.py mint` directly; `sancai_decide.py mint` is the only path, and
the hook forces the native permission prompt. If `SANCAI_SECRET` is not set, stop
and report: the plugin is not a sandbox.

---

## accept (H3)

Render the acceptance card; do not narrate it yourself:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/sancai_card.py" accept --run <run>
```

The card's flow map marks `H3 accept`; the full upstream path stays visible so
the human accepts the outcome in context, not in isolation. Before asking, add
your own ASCII diagram of what was implemented: changed surface → checks and
evidence → gate/verifier verdicts → what was intentionally left out
(non-goals). This is the "show the finished work" diagram; there is no fixed
format, but every node must trace to a file, command, gate result, or verdict.

Preconditions: run is `reviewing`; all Work Orders `verified` or `merged`;
every requirement selected in the intent has at least one verified Work Order.

Show only:

- Work Orders and gate results
- AC coverage
- requirement coverage (`REQ-*` → verified WOs)
- backlog items captured during this run
- evidence paths
- open findings
- what was **not** done (non-goals)

Do not show the raw diff unless asked.

Require an explicit acceptance word (`accept` / `accepted` / `confirmed`) in the
human's reply. The agent passes the rendered card id/code; the human clicks
Allow in Claude Code's permission prompt. A bare `ok` or `1` is not acceptance.

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/sancai_decide.py" accept \
  --run <run> --message "<verbatim>" --session-id "${CLAUDE_CODE_SESSION_ID:-}" \
  --card-id <CARD-ID> --card-code <CODE>
```

The accept card binds the run state, every Work Order state, gate results, and
the findings hash. If verdicts contain findings, acceptance is refused until
the human acknowledges them:

```bash
  --ack-findings
```

Major findings require exactly one disposition in addition:

```bash
  --ack-findings --disposition "defer:<FOLLOWUP-ID>"    # capture a backlog TODO
  --ack-findings --disposition "waive:<reason>"   # accept the risk explicitly
```

`defer:<FOLLOWUP-ID>` must be a new, unused id. It captures a `finding` TODO in
`.sancai/project/backlog.json`
sourced to `run:<run>/WO:<WO-ID>`. It does **not** create a new Work Order in
the accepted run; the human promotes it later if it should be planned.

Blocking (blocker/critical) findings can never be accepted. If the human
refuses acceptance, do not record an accept: keep the run in `reviewing`,
record their reason (e.g. as a new escalation or progress note), and send the
Work Order back for rework. A consumed card is single-use — each attempt needs
a freshly rendered card.

Merge/deploy is a separate irreversible action; use `/sancai approve` if needed.

---

## status

Read-only:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/sancai_state.py" status
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/sancai_graph.py" position --run <run>
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/sancai_graph.py" show --run <run>
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/sancai_escalate.py" list --run <run>
```

Show:

```
Run: <run>   State: <state>   Layer: <L3/L2/L1>   Progress: <verified>/<total>
Trigger: <ESC-ID or ->
Open escalations: <n>

Work Orders
  WO-001  verified   reversible=true   files=2   evidence=yes gate=verified
```

---

## abandon

Abandoning is a legitimate terminal state. It is a human decision: call the
native entrypoint and let the hook show the permission prompt.

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/sancai_decide.py" abandon \
  --run <run> --reason "<verbatim reason>"
```

Report: run id, reason, what was completed, what remains, evidence paths.
Do not delete `.sancai/runs/<run>/`; the audit trail must survive.


## Status and progress

`/sancai status` prints the state, layer, progress, next step, and open
escalations. For a read-only progress card with recent events, run
`sancai_card.py status --run <run>`; for the audit trail, run
`sancai_graph.py timeline --run <run> --last 20`.
