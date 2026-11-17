# Team Invariants — How this process implements them

> For the methodology definition, see [team-invariants.md](../../agent-team-authoring/references/team-invariants.md).
> This file only explains **how this process mechanically enforces them**; it does not repeat the definitions.

| # | Invariant | Mechanical guarantee in this process |
|---|---|---|
| T-1 | **Files over context** | Each phase has mandatory artifact files; `SubagentStop` validates the report contains `verdict`; `Stop` validates the mission reaches `verified` |
| T-2 | **Own your files** | `PreToolUse` reads `claim.files` in `flow.json`; out-of-bounds writes get `deny` |
| T-3 | **Liveness is receipt** | On resume, do not assume a teammate is still alive; recovery only counts after re-spawning and receiving this session's first receipt |
| T-4 | **Keep checkpoint** | `PreCompact` blocks in `executing`/`reviewing` when there is no snapshot within 30 minutes; `bash "${CLAUDE_PLUGIN_ROOT}/scripts/flow.sh" checkpoint` is the only entry point |
| T-5 | **Lead coordinates** | PM is the only role that may call `bash "${CLAUDE_PLUGIN_ROOT}/scripts/flow.sh" transition` and write `team-plan.md`/`decisions.md`; teammates may only suggest |

## Three commonly violated scenarios

### Scenario 1: PM casually changes a line of code

- **Why wrong**: violates T-5 and breaks the separation of "implementer has full context, verifier has no implementation context"
- **Mechanical interception**: while dispatching work the PM's `claim` is non-empty; writing a source path outside the claim → `deny`
- **Only exception**: XS-level fixes (comments, spelling), and they must be recorded in `decisions.md`

### Scenario 2: reviewer fixes it themselves

- **Why wrong**: violates T-5 and essence I-5; a verifier that becomes an implementer loses independence
- **Mechanical interception**: the reviewer's `tools` include Write, but its lane only allows its own section of `findings.md`
- **Alternative action**: write a finding + `fix` suggestion; the executor implements it

### Scenario 3: continuing from memory after interruption

- **Why wrong**: violates T-1 and T-3. `flow.json` on disk only says "how far last time", not "who is alive now"
- **Mechanical interception**: the recovery procedure forces `bash "${CLAUDE_PLUGIN_ROOT}/scripts/flow.sh" status` first, then reading `dead-ends.md`, then re-spawning
- **Criterion**: no receipt from this session = does not exist

## Handling violations

| Violation type | Handling |
|---|---|
| Out-of-bounds write rejected by hook | Record in `findings.md`; do not retry the same path |
| Report missing verdict rejected | Complete it and resend (required while a claim is active); 2 consecutive times counts as 1 failure of the unit |
| Stop blocked | Continue per the emitted `next` suggestion; do not bypass the hook |
| Resume not per protocol | That round is void; re-form the team from N3 |
