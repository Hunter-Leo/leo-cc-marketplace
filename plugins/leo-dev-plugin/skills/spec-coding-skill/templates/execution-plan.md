# Execution Plan — [NNN]-[req-name]
**Round:** [N]
**Status:** draft

## 1. Available Agent Types
(from session context)

| Type | Description | Selected | Role |
|------|-------------|----------|------|
| [type] | [description] | Yes/No | Execution / Review / ... |

## 2. Execution Mode & Phase Plan
**Mode:** [Dual Agent / Single Agent / Team / OMC Skill]

**Task breakdown by phase:**

| Phase | Tasks | Description | Reviewer Checkpoint |
|-------|-------|-------------|-------------------|
| 1 | T-001 ~ T-00X | [description] | After phase |
| 2 | T-00Y ~ T-00Z | [description] | After phase |

**Rationale:** [why this mode fits this round]

## 3. Agent Setup & Startup Prompts

### Agent 1: [name] — [role]
- **Type:** [agent type]
- **Assigned tasks:** T-001 ~ T-00X
- **Startup prompt:**
  ```
  You are [role] in requirement [NNN]-[req-name].

  Read these documents before any work:
  1. shared/00-agent-execution.md — global rules (self-check, deviation protocol)
  2. shared/02-coding-standards.md — code/comment/test standards
  3. shared/03-git-workflow.md — branch naming, commit format, pre-commit checks
  4. phase-b/00-start-and-resume.md § Execution Loop — 12-step procedure
  5. phase-b/00-start-and-resume.md § Phase B Execution Discipline — no implicit fallback, no mock internal/external
  6. phase-b/01-round-mechanism.md — state machine, deviation decision matrix
  7. spec-coding-skill/SKILL.md — full methodology, round mechanism, core rules

  Prohibited: implicit fallback (no silent catch, no hidden retry, no log-and-continue past real errors).
  Integration tests: do NOT mock internal modules or real external dependencies.
  ```

### Agent 2: [name] — [role]
...

## 4. Confirmation
- [ ] User approved execution plan
- [ ] All agent prompts aligned
