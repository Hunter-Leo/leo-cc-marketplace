# Communication and Handoff

> Agents do not share history. All "collaboration" ultimately lands on three channels; choosing the wrong channel loses information or auditability.

## 1. Three Forms of Communication

| Form | Mechanism | Applies to | Not suitable for |
|---|---|---|---|
| **Natural language** | SendMessage free text | clarification, negotiation, exploratory discussion | handoff artifacts, state transitions, auditable decisions |
| **Structured call** | SendMessage with fixed fields / script call | dispatching tasks, receipts, state transitions, ping | complex explanations, open-ended discussion |
| **Shared files** | disk paths | artifacts, decisions, research, snapshots, dead-end records | short-term sync, gate confirmation |

Selection rule:

```text
need evidence          → shared files
need to drive the flow → structured call
just asking one thing  → natural language (and must be persisted afterward)
```

**Every conclusion reached in natural language must land in a file before the end**, otherwise it is treated as never happened (team-invariants T-1).

## 2. Return Contract (Fixed Format)

Must be returned at the end of every task; field names exactly match `../../spec-coding-team-skill/references/rails.md` R-10, no additions or removals:

```yaml
verdict: PASS | FAIL | BLOCKED
artifacts: [paths...]          # paths only, do not paste content
findings:
  - severity: blocker | critical | major | minor | nit
    file: path:line
    evidence: <command output / phenomenon>
    fix: <suggestion>
contract_for_next: <interface/assumption downstream needs to know, one sentence>
next_action: <suggested next step>
stop_reason: <why it ended>
```

Key points:

- Missing `verdict` → the return is not consumable and the state machine disallows transitions (the `SubagentStop` hook rejects it).
- While a claim is active, `verdict`, `artifacts`, and `stop_reason` must also be persisted to `.team/<run>/verdicts/<unit-id>.json`. A conversation-only return is blocked by the `SubagentStop` hook, even when the text itself contains a verdict.
- `artifacts` holds paths only. Pasting full text contaminates downstream context with upstream content and cannot be versioned.
- `contract_for_next` is the only field allowed to carry "non-persisted information", so it must be short, must be one sentence, and must contain only assumptions downstream cannot read from the artifacts.
- `stop_reason` distinguishes "finished" from "gave up" — both may be PASS/FAIL, but the handling differs.

## 3. Primer Dossier

A self-contained startup package that must be prepared before spawn. **Claude Code has no SubagentStart event**; there is no mechanism for "teammates to read automatically on startup" — the primer must be **given explicitly in the spawn prompt**.

Must contain six items:

| # | Content | Why required |
|---|---|---|
| 1 | Organizational context: where this team sits in the overall process, current mission state | otherwise the role doesn't know which step it is on |
| 2 | Team members: who is who, each one's lane | otherwise it doesn't know whom to ask, or who is writing the same area |
| 3 | Skill summary per role: which files **this role** should read, which not to read | control the context budget; prevent reading contaminated process records |
| 4 | Goals and acceptance criteria | a role without acceptance criteria will invent its own |
| 5 | Deployment steps: what to read first, what to do next, when to report back | the only basis for behavior on cold start |
| 6 | Invariants: files are state, pass paths only, write boundaries, completion means verification | team runtime discipline |

**Budget: 6000 characters.** When exceeded, trim in the following order:

```text
first delete narrative content of the organizational background (keep one line of state)
then delete résumé-style descriptions of team members (keep lane and archetype)
do not delete acceptance criteria
do not delete invariants
do not delete deployment steps
```

The primer is a file repeatedly injected into teammate contexts. **External content must never enter the primer** (`../../spec-coding-team-skill/references/rails.md` R-7) — it is a high-value target for prompt injection.

## 4. DEAD_ENDS

Records **excluded approaches and the reasons**, format:

```markdown
## Excluded
- <approach> — excluded on <date> — reason: <one sentence> — evidence: <path:line / command output>
```

Rules:

- Any rejected approach goes into DEAD_ENDS, not just into the conversation.
- **The first thing to do after resuming is to read it.** Otherwise the resumed agent re-walks a path already proven impassable, at double the token cost.
- Exclusions without reasons must not be written — "feels wrong" is not a dead-end record, it is noise.

## 5. Cross-Session Resume Protocol

Five fixed steps, no skipping:

```text
1. Validate the registry
   - do the roles still exist
   - does the lane match the current plan
   - are there roles that have been removed but are still in state

2. Filter the wake set
   - only wake units in non-terminal states (in_progress / for_review / changes_requested / pending)
   - do not wake merged/verified ones

3. spawn
   - explicitly attach the primer in the spawn prompt (no SubagentStart event)

4. Read the trio
   - primer (discipline and goals)
   - snapshot (where this unit stopped last time)
   - DEAD_ENDS (paths not to walk again)

5. Receipt fixed as Resumed
   - content: unit / last state / the first thing to do this time
```

The most common cause of resume protocol failure: skipping step 1. A stale registry makes the system wake a role whose lane has been reassigned, causing two agents to write the same file.

## 6. Channel Cost Comparison

| Channel | Latency | Auditable | Context cost |
|---|---|---|---|
| natural language | low | none | medium (full text enters context) |
| structured call | low | field-level | low |
| shared files | medium (disk write) | complete | on demand at read time |

Conclusion: **by default use structured calls to drive the process, shared files to carry facts, and natural language for exceptions.** Doing it in reverse (free text by default, files patched afterward) is the starting point of team collaboration degradation.
