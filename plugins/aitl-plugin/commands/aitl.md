---
description: "AITL entrypoint. Humans only need five subcommands: start / approve / accept / status / abandon. Run and check are executed automatically by the harness."
argument-hint: "start <goal> | approve <escalation> | accept | status | abandon <reason>"
---

# /aitl

You are the AITL entrypoint. Before acting, load
`${CLAUDE_PLUGIN_ROOT}/skills/aitl-harness/SKILL.md`.

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
no .aitl/active                     → start
active run + open escalation        → show it, ask to approve
active run, state=reviewing         → show summary, ask to accept
active run, state=executing         → status + next action
active run, state=accepted/abandoned→ status
```

**Do not ask the human to type `run` or `check`.** Those are internal.

When a run is active, render the card first:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/aitl_card.py" current --run <run>
```

It auto-detects intent / approve / out-of-scope / ambiguous / accept / blocked,
and prints "No action needed from you" when no human action is needed.

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

## start (H1 + automatic loop)

### 1. Draft the intent

Create `.aitl/runs/<run>/intent.json`:

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
  "budget": {"human_rounds": 3, "wall_clock": "2d", "tokens": 2000000}
}
```

Validate:

- every AC has an executable `run` and a concrete `expect`
- manual AC is forbidden by default; exceptions need a written reason and total ≤ 20%
- reject vague criteria

### 2. Initialize (state=planning)

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/aitl_state.py" init \
  --run <run> --intent .aitl/runs/<run>/intent.json --session-id "${CLAUDE_SESSION_ID:-}"
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/aitl_state.py" activate --run <run>
```

### 3. Render the intent card and confirm (human gate H1)

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/aitl_card.py" intent --run <run>
```

Present the card, then use the interactive question UI (Start / Edit / Cancel).
This is the default H1 path: the human does not copy card ids or run a command.

- If the human chooses **Start**, call the agent-allowed recorder with the
  human's exact choice:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/aitl_state.py" record-intent \
  --run <run> --session-id "${CLAUDE_SESSION_ID:-}" --message "confirmed"
```

- If the human chooses **Edit** or **Cancel**, update the intent or stop; do not
  record an approval.

H1 is a contract gate, not proof of an irreversible action. For high-risk runs
(`T3`/`T4`, or `AITL_REQUIRE_TTY_SIGN=1`), use the native decision entrypoint;
the PreToolUse hook turns it into Claude Code's permission prompt, so the human
clicks Allow instead of copying a command:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/aitl_decide.py" sign \
  --run <run> --session-id "${CLAUDE_SESSION_ID:-}" --message "confirmed" \
  --card-id <CARD-ID> --card-code <CODE>
```

`aitl_human.py sign` remains the T4/terminal-only path when the repository
requires a real TTY process.

### 4. Run the loop automatically

Do this without asking the human to type commands:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/aitl_state.py" transition --to executing
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/aitl_state.py" add-wo --id WO-001 \
  --files "<exact paths>" --reversible true
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/aitl_state.py" claim --wo WO-001 --by executor
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/aitl_state.py" progress \
  --wo WO-001 --status doing --item "executor dispatched"
```

Then spawn **`aitl-executor`** with:

- the Work Order id and `owned_files`
- the acceptance criteria excerpt
- `${CLAUDE_PLUGIN_ROOT}/references/coding-standards.md`
- `${CLAUDE_PLUGIN_ROOT}/references/git-workflow.md`
- `${CLAUDE_PLUGIN_ROOT}/references/progress-updates.md`

After the executor reports:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/aitl_check_ac.py" --run <run> --wo WO-001
```

Then spawn **`aitl-verifier`** with the raw evidence + AC + diff (never the executor's narrative). The verifier writes its verdict through `aitl_verdict.py` with a fresh `--context-id` (different from the executor and its claim) and a `--prompt-hash`; a pass verdict carrying a blocker/critical finding is rejected.

Then:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/aitl_gate.py" --run <run> --wo WO-001 --apply
```

### 5. Stop only on the three triggers

Ask the human only when:

1. **irreversible** — delete, force-push, pay, deploy, change permission
2. **out_of_scope** — outside `owned_files`, new dependency, production access
3. **spec_ambiguous** — AC conflict or missing definition

Everything else (style, naming, normal test failures, reversible refactors) is the executor's job.

### 6. Report

When the run reaches `reviewing`, report:

- Work Orders and gate results
- evidence paths
- open findings
- ask for `/aitl accept`

---

## approve (H2)

1. Render the approval card; do not narrate it yourself:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/aitl_card.py" approve --run <run> --esc <ESC-ID>
```

2. Show the **raw operation**: exact action, arguments, target, diff hash, why it is irreversible, what cannot be undone.
3. Require explicit `confirmed` / `confirmed` / `approved` / `approved` **plus the card id/code**. A bare number (`1`), `ok`, or a reply without the card pair is **not** approval for an irreversible action; ask the human to reply with the word and the card footer.
4. Mark the escalation approved with the rendered card. Call the native
decision entrypoint; the hook returns `permissionDecision: "ask"`, so Claude
Code shows its permission prompt. The human clicks Allow; they do **not** copy
a command:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/aitl_decide.py" approve \
  --run <run> --id <ESC-ID> --message "<verbatim>" \
  --session-id "${CLAUDE_SESSION_ID:-}" \
  --card-id <CARD-ID> --card-code <CODE>
```

If the human rejects, record the reason instead (same card binding and native
prompt):

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/aitl_decide.py" reject \
  --run <run> --id <ESC-ID> --reason "<verbatim>" \
  --session-id "${CLAUDE_SESSION_ID:-}" \
  --card-id <CARD-ID> --card-code <CODE>
```

A rejection needs a concrete reason; silence or a bare `no` is not enough.
Never reuse an approval card for another escalation or another round.

5. Mint a one-time token. This also goes through the native prompt; the human
sees the exact action and diff before clicking Allow:

```bash
AITL_SECRET="<from keychain/env, never from the repo>" \
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/aitl_decide.py" mint \
  --run <run> --action "<action>" --diff-sha "<sha>" --ttl 600
```

6. Hand the token to the privileged executor. The agent cannot call
`aitl_capability.py mint` directly; `aitl_decide.py mint` is the only path, and
the hook forces the native permission prompt. If `AITL_SECRET` is not set, stop
and report: the plugin is not a sandbox.

---

## accept (H3)

Render the acceptance card; do not narrate it yourself:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/aitl_card.py" accept --run <run>
```

Preconditions: run is `reviewing`; all Work Orders `verified` or `merged`.

Show only:

- Work Orders and gate results
- AC coverage
- evidence paths
- open findings
- what was **not** done (non-goals)

Do not show the raw diff unless asked.

Require explicit `accept` / `accepted` / `accepted` / `accepted` / `confirmed` **plus the card id/code**. A bare `ok` or `1`, or a reply without the card pair, is not acceptance. Call the native decision entrypoint; the human clicks Allow in Claude Code's permission prompt:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/aitl_decide.py" accept \
  --run <run> --message "<verbatim>" --session-id "${CLAUDE_SESSION_ID:-}" \
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
  --ack-findings --disposition "defer:<WO-ID>"    # create a follow-up WO
  --ack-findings --disposition "waive:<reason>"   # accept the risk explicitly
```

Blocking (blocker/critical) findings can never be accepted. If the human
refuses acceptance, do not record an accept: keep the run in `reviewing`,
record their reason (e.g. as a new escalation or progress note), and send the
Work Order back for rework. A consumed card is single-use — each attempt needs
a freshly rendered card.

Merge/deploy is a separate irreversible action; use `/aitl approve` if needed.

---

## status

Read-only:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/aitl_state.py" status
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/aitl_graph.py" position --run <run>
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/aitl_graph.py" show --run <run>
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/aitl_escalate.py" list --run <run>
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

Abandoning is a legitimate terminal state.

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/aitl_state.py" abandon --reason "$ARGUMENTS"
```

Report: run id, reason, what was completed, what remains, evidence paths.
Do not delete `.aitl/runs/<run>/`; the audit trail must survive.


## Status and progress

`/aitl status` prints the state, layer, progress, next step, and open
escalations. For a read-only progress card with recent events, run
`aitl_card.py status --run <run>`; for the audit trail, run
`aitl_graph.py timeline --run <run> --last 20`.
