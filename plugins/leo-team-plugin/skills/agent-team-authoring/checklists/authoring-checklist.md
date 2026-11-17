# Team Design Self-Check Checklist

> 12 items. The "evidence" for each must be **an artifact a third party can review**, not "whether it was considered".
> If any item cannot produce evidence → the design is not complete; do not enter spawn.

- [ ] **1. The team verdict is written out, with a reason**
  - Check: one line `Conclusion: agent_teams | workflow | single_session — reason: <one sentence>` exists in the design document
  - Evidence: the original text of that line
  - Failing example: only "need a team", no reason

- [ ] **2. Each role belongs to exactly one archetype**
  - Check: no empty or composite values in the archetype column of the role table (e.g. "Builder+Adversary")
  - Evidence: original text of the role table
  - Failing example: a role that "implements and reviews its own code"

- [ ] **3. No role is named or split by technical layer**
  - Check: role names and responsibilities do not use "frontend/backend/test/ops/DBA" as the basis of decomposition
  - Evidence: role name list + archetype of each role
  - Failing example: `frontend-agent`, `test-agent`

- [ ] **4. Lanes are parsable globs and pairwise disjoint**
  - Check: the sets of writable paths of parallel roles do not intersect
  - Evidence: `bash "${CLAUDE_PLUGIN_ROOT}/scripts/check-lanes.sh"` output (`exit 0` and no potential overlap, or manual confirmation for each WARN)
  - Failing example: "responsible for the order module" (not machine-parsable)

- [ ] **5. Every role has an Output contract containing the fixed return format**
  - Check: the persistence path is declared; return fields are verdict / artifacts / findings / contract_for_next / next_action / stop_reason; while a claim is active, `.team/<run>/verdicts/<unit-id>.json` is persisted with at least `{verdict, artifacts, stop_reason}` (conversation-only returns are blocked by the `SubagentStop` hook)
  - Evidence: the `## Output contract` section of the role card + the verdict-file path
  - Failing example: only "report when done", or a verdict that exists only in the conversation

- [ ] **6. Every role has executable Done criteria**
  - Check: each judgment contains a command or numeric threshold, re-runnable by a third party
  - Evidence: command list (a rough check is possible with `grep -c '`'`)
  - Failing example: "functionality normal, code clean"

- [ ] **7. Team size is between 2–4 (coordinators excluded)**
  - Check: implementation/review/verification role count ≤ 4; when over the limit, the reason for reduction must be recorded
  - Evidence: role count
  - Failing example: 6 roles with no scale rationale

- [ ] **8. Phase gates can only be initiated by the lead to the user**
  - Check: only one role's Escalation section contains "ask the user for confirmation"; other roles can only report to the lead
  - Evidence: each role's `## Escalation` section
  - Failing example: the verifier can directly announce completion to the user

- [ ] **9. A primer exists, ≤ 6000 characters, with six elements**
  - Check: [templates/primer.md](../templates/primer.md) was used; organizational context / team / skill summary / goals and acceptance / deployment steps / invariants
  - Evidence: `wc -m` output + the six subsection headings
  - Failing example: 3200 characters but missing "deployment steps"

- [ ] **10. The DEAD_ENDS file exists and its format is compliant**
  - Check: each entry contains `approach / date / reason / evidence`
  - Evidence: file path + one sample entry
  - Failing example: only "not considering X for now" with no reason

- [ ] **11. State transitions are validated by a script, which can reject illegal transitions**
  - Check: `scripts/flow.sh` exists and its `transition` subcommand rejects an illegal target with exit 1; there is measured output of one rejected transition
  - Evidence: `bash "${CLAUDE_PLUGIN_ROOT}/scripts/flow.sh" transition --unit <id> --to approved` on a `pending` unit, plus the exit code and stderr
  - Failing example: states only in a document, judged by the agent itself

- [ ] **12. External content has a path whitelist, and key constraints are labeled by layer**
  - Check: external content may only be written to research/findings; each hard constraint is labeled L1/L2/L3
  - Evidence: path whitelist + constraint-layer mapping table
  - Failing example: pasting web page summaries into the primer or team-plan

---

## Usage Notes

- When checking item by item, **write the evidence path or command after the item**; a checkmark alone does not count as done.
- Items 4, 9, and 11 can be scripted directly; it is recommended to codify the commands into CI or hooks.
- Passing all 12 still does not guarantee the design is correct; it only guarantees **the design has no structural gaps**; correctness still needs validation by one real task.
