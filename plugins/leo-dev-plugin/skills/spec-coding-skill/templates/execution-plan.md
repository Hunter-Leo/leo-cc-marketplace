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
  1. references/phase-b-agent-brief.md — condensed brief covering all Phase B rules (read first)
  2. phase-b/02-execution-loop.md — full 12-step procedure and deviation protocol
  3. spec-coding-skill/SKILL.md § Core Rules — skill-specific mandatory rules

  Full reference documents (shared/00-agent-execution.md, shared/02-coding-standards.md, shared/03-git-workflow.md, phase-b/01-round-mechanism.md) are available on-demand. The Agent Brief covers the essentials for all of them.

  Prohibited: implicit fallback (no silent catch, no hidden retry, no log-and-continue past real errors).
  Integration tests: do NOT mock internal modules or real external dependencies.
  ```

### Agent 2: [name] — [role]
...

## 4. Confirmation
- [ ] User approved execution plan
- [ ] All agent prompts aligned
