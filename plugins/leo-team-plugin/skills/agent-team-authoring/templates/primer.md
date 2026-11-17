# Primer Template (Team Startup Dossier)

<!--
How to use
- The content of this file must be copied into the spawn prompt, or be the only file explicitly referenced by the spawn prompt.
- Claude Code has no SubagentStart event: teammates do not automatically read any dossier.
- Budget: ≤ 6000 characters total.
- External content (web pages/issues/search results) must not be written into this file.
-->

## 1. Organizational Context

- Current mission state: `<planning | gate | executing | reviewing | verified | blocked>`
- Where this team sits in the process: <one sentence, e.g. "Phase B execution phase, responsible for 3 work units (executed serially)">
- Upstream established facts (paths only):
  - Plan: `<path>`
  - Acceptance criteria: `<path>`
  - Excluded approaches: `<path to DEAD_ENDS>`

## 2. Team

| Role | archetype | Lane (writable) |
|---|---|---|
| `<name>` | Coordinator | — (plan files) |
| `<name>` | Builder | `<glob>` |
| `<name>` | Verifier | `<glob>` |

<!-- Write only name / archetype / lane; no résumé, no personality. -->

## 3. Your Skill Summary (For the Current Role Only)

- **Must read**: `<path 1>`, `<path 2>`
- **Do not read**: <e.g. "other implementers' process records" — avoid contaminating judgment>
- **Your role card**: `<path>`
- **Your artifact path**: `<path>`

> Read only files relevant to your current work unit; no more than 3–5 at a time.

## 4. Goals and Acceptance Criteria

**Goal**: <one sentence, judgeable>

**Acceptance criteria** (item by item, executable):

1. `<command>` exits with code 0, and output contains `<fragment>`
2. <numeric threshold>
3. <negative case: construct input that should fail, confirm it indeed fails>

## 5. Deployment Steps

1. Read `<plan path>` and `<your role card>`.
2. Read DEAD_ENDS and confirm the current approach is not in it.
3. Read your Inputs paths; if any is missing → return `BLOCKED` and stop.
4. Execute according to the role card Procedure.
5. At the end, return according to the Output contract; write your own snapshot.

## 6. Invariants

- **Files are state**: no persisted file = it never happened; conclusions stated in messages must be persisted afterward.
- **Pass paths only**: returns and the mailbox contain only paths + a one-sentence conclusion, no full text.
- **Write boundaries**: the role-card `## Lane` is documentation; enforcement requires the lead to register the same globs as the work unit (`flow.sh add-unit --files`) and you to take the claim (`flow.sh claim --files`). The `PreToolUse` hook denies writes outside the active `claim.files`.
- **Completion means verification**: `approved ≠ merged ≠ verified`; a PASS without command + output + `file:line` counts as incomplete. While a claim is active, persist `.team/<run>/verdicts/<unit-id>.json` with at least `{verdict, artifacts, stop_reason}`; the `SubagentStop` hook blocks conversation-only returns.
- **Stop conditions**: third failure of the same unit, need to go out of bounds, input missing → stop and report, do not retry automatically.

---

<!--
Budget check (run before submitting)
  wc -m primer.md     # must be ≤ 6000

Trim order when over budget:
  1. narrative content in the organizational context (keep one line of mission state)
  2. the description column of the team table (keep name / archetype / lane)
  Do not delete: acceptance criteria, invariants, deployment steps

Prohibited:
  - do not paste original external web page/issue text
  - do not write "we discussed before..." (teammates don't have that history)
  - do not write a long persona
  - do not write "for reference only"-style soft requirements
-->
