# spec-coding-skill

A spec-driven methodology for LLM agents to define, plan, and implement coding work with quality and consistency.

## Overview

The skill uses **round-based iterative execution** — when problems arise during implementation, they are logged and resolved in subsequent rounds rather than silently deviating from the plan. Includes automatic **task sizing** — trivial fixes skip document ceremony, while complex features get the full structured flow.

## Workflow

```
Task Sizing  (XS → direct, S → light, M+ → full phases)
     │
     ▼
Phase 01 — Initialization           (init.md)
     ↓
Phase 02 — Prerequisite Tasks       (research/inspect/diagnose — optional)
Phase 03 — Algorithm Design         (optional)
     ↓
Phase 04 — Implementation Plan     (plan.md)
     ↓
Phase 05 — Task Planning           (tasks.md)
     ↓
Phase 06 — Resume Setup            (start-and-resume.md)
     ↓
Phase 07 — Execution               (code)
     │
     ▼
Round Review → issues? → Round N+1 → Done
```

## Task Sizing

| Size | When | Ceremony |
|------|------|----------|
| XS | 1 file, trivial change | Brief init.md + inline plan → implement → test → commit |
| S | 1-3 files, well-defined | Light init.md (Spec + Requirements + Plan) → implement → test → commit |
| M | Multi-module feature | Full Phase 01-07 flow |
| L/XL | Cross-requirement | Full flow + Blueprint + Phase 02 mandatory |

## Best Practices

### 1. Always let task sizing run first

Even if the request seems simple, let the skill determine the size. It catches edge cases where "simple" changes have far-reaching effects.

### 2. Follow the Phase Transition Re-read Discipline

Before entering any phase, the agent **must** re-read that phase's reference file. This is not optional — it prevents the agent from operating on stale context.

### 3. Use methods when triggers match

Methods like TDD, Structured Debugging, and Dual-Axis Review have explicit trigger conditions. If they match, apply them. "Not needed" without justification is invalid.

### 4. Never silently deviate from plan.md

If implementation reveals something different from the plan, stop and log a deviation. See the Deviation Protocol in `00-start-and-resume.md`.

### 5. Keep the blueprint up to date

`.dev/blueprint.md` tracks all requirements across rounds. Update it at every phase transition.

### 6. Round history matters

Each round builds on the previous one. `issues.md` drives the N+1 loop — don't skip it.

## Files Generated

```
.dev/
├── blueprint.md              ← Cross-requirement roadmap
├── <NNN>-<req-name>/
│   ├── init.md               ← Spec + Requirements + Action Items
│   ├── plan.md               ← Implementation plan
│   ├── tasks.md              ← Task breakdown
│   ├── start-and-resume.md   ← Session bootstrap
│   └── issues.md             ← Open/closed issues (drives rounds)
```

## Reference Architecture

| Area | File |
|------|------|
| Agent rules (read first) | `references/constitution/00-agent-execution.md` |
| OOP & SOLID | `references/constitution/01-oop-principles.md` |
| Coding standards | `references/constitution/02-coding-standards.md` |
| Git workflow | `references/constitution/03-git-workflow.md` |
| Round mechanism | `references/execution/01-round-mechanism.md` |

## Method Reference

| Method | Phase | When |
|--------|-------|------|
| Term Grilling + ADR | 01 / 02 / 04 | Fuzzy terms, hard decisions |
| Vertical Slice TDD | 07 | Clear public interfaces |
| Dual-Axis Review | Round end / PR | Significant code review |
| Architecture Deepening | 02 | Shallow modules |
| Structured Debugging | 02 | Non-trivial bugs |
