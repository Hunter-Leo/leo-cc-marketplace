---
name: spec-coding-skill
description: "Guides LLM agents through large-scale coding tasks using a two-phase methodology: Phase A (需求构建阶段, initialization through planning) and Phase B (需求执行阶段, execution through review), connected by a hard user-confirmation gate. Covers requirement definition, planning, algorithm design, implementation, deviation handling, and round-to-round issue tracking. Includes OOP/SOLID principles, language-specific coding standards, a dual-layer state machine for flow decisions, and trigger-driven extended methodologies for TDD, structured debugging, architecture deepening, terminology alignment, and dual-axis review. This skill should be used when the user asks to 'start a coding task', 'plan implementation', 'begin a new requirement', 'enter execution phase', 'resume a project', or mentions spec-driven development, round-based execution, or the spec-coding-skill flow. Keywords: spec-driven development, round-based execution, iterative development, deviation protocol, state machine, coding methodology, software engineering workflow, requirements-to-code pipeline, project blueprint, TDD, debugging, architecture review, method selection, phase-a, phase-b."
triggers:
  - spec-driven
  - coding task
  - development workflow
  - requirements
  - implementation plan
  - coding standards
  - software project
  - phase-by-phase
  - OOP
  - SOLID
  - round
  - iteration
  - deviation
  - state machine
  - iterative
  - iterative development
  - tdd
  - debugging
  - architecture review
  - code review
  - bug diagnosis
  - term alignment
  - ADR
metadata:
  version: "2.0"
---

# Spec Coding Skill

A spec-driven methodology for LLM agents to define, plan, and implement coding work with quality and consistency. Uses **round-based iterative execution** — when problems arise during implementation, they are logged and resolved in subsequent rounds rather than silently deviating from the plan. Includes automatic **task sizing** — trivial fixes skip document ceremony, while complex features get the full structured flow.

## STOP — Mandatory Startup Sequence

> **Do each step in order. Do not skip any step. Each step is a hard gate — the next step depends on information from the previous one.**

### Step 1 — Read Global Agent Rules (DO NOT SKIP)

**MUST** read [shared/00-agent-execution.md](shared/00-agent-execution.md) before doing anything else. This file defines rules that override all phase-specific instructions: Task Sizing, Phase Transition Re-read Discipline, Self-Check, Deviation Protocol, and Round-based Execution Model. **If you skip this file, you will miss mandatory rules and violate the process.**

### Step 2 — Check Project State

Check if `.dev/blueprint.md` exists:

| Blueprint exists? | Action |
|---|---|
| **Yes** | Run the [Session Bootstrap](phase-b/00-start-and-resume.md#session-bootstrap-new-agent-session-on-existing-project). Present full project status, then resume the active requirement. |
| **No** | Proceed to Step 3 (new requirement). |

### Step 3 — Task Sizing (MANDATORY)

Run [Task Sizing](shared/00-agent-execution.md#task-sizing) to determine workflow depth. Announce the size to the user before proceeding.

| Size | Workflow |
|------|----------|
| **XS** (1 file, trivial) | Brief `init.md` with inline plan → implement → test → commit |
| **S** (1-3 files, well-defined) | Lightweight `init.md` (Spec + Requirements + Plan) → implement → test → commit |
| **M** (multi-module) | Full Phase 01–07 flow |
| **L/XL** (cross-requirement) | Full flow + Blueprint layer + Phase 02 mandatory |

### Step 4 — Phase Transition Rules (applies to ALL phases)

Before entering ANY phase, you MUST:

1. **Re-read the phase reference file** — see [Phase Transition Re-read Discipline](shared/00-agent-execution.md#phase-transition-re-read-discipline) for the exact file per phase. Never enter a phase cold.
2. **Run Method Selection** — evaluate every method tagged for that phase against trigger conditions. Apply if triggers match; provide specific factual justification if they don't. See [Method Selection](#method-selection--trigger-driven) below. Generic "not needed" is invalid.

### Step 5 — Enter Phase 01

Follow [phase-a/00-initialization.md](phase-a/00-initialization.md). XS/S: Pre-flight Checks then lightweight init.md. M+: full init.md with Spec, Requirements, Action Items, Constitution.

### Step 6a — Phase A: 需求构建阶段

Proceed through Phase 02–06. At each phase entry, repeat Step 4 (re-read phase doc + run Method Selection).

After Phase 06 completes, proceed to the Phase A→B Gate below.

### Step 6b — Phase A→B Gate: 用户确认门 (HARD GATE)

DO NOT enter Phase 07 until the user explicitly confirms the Phase A→B proposal.
The proposal MUST include the following in **one message**:

1. **Phase A documents summary** — what docs were produced, key highlights
2. **Execution mode** — recommended mode (default: 执行 Agent + Review Agent, auto-advance; see [phase-b/00-start-and-resume.md](phase-b/00-start-and-resume.md) § Execution Mode Recommendation)
3. **Branch name** — auto-generated from requirement name `<type>/[NNN]-[req-name]`

User confirms once → Agent creates branch automatically → enters Phase B.
User asks for changes → iterate all items, re-present.
After user confirmation, update `.dev/blueprint.md`: set Phase to `07 Execution`, Status to `▶ in-progress`.

GATE RULE: "Looks good" without explicit confirmation of all items is NOT sufficient.
Ask: "Do you confirm the docs, branch name, and execution mode? Reply **confirmed** to proceed."

### Step 6c — Phase B: 需求执行阶段

After the gate is passed, enter Phase 07. Phase B execution is governed
by [Phase B Execution Discipline](phase-b/00-start-and-resume.md#phase-b-execution-discipline).

### Step 7 — Round Review (MANDATORY after Phase 07)

Check `issues.md`. Open issues → re-enter Phase 01 for Round N+1. No open issues → done.

Execution is **round-based**: problems found during a round are captured in `issues.md` and resolved in the next round, not silently fixed mid-flight. See [phase-b/01-round-mechanism.md](phase-b/01-round-mechanism.md) for the state machine and decision matrix.

All generated documents go under `.dev/[NNN]-[req-name]/` in the project root.

## Phase Overview

```
              ┌──────────────────────────┐
              │    Task Sizing           │  ← mandatory first step
              │  XS → direct implement   │     (see 00-agent-execution.md)
              │  S  → minimal init.md    │
              │  M+ → Phase 01-07 below  │
              └──────────────────────────┘
                          │ (M+ only)
                          ▼
Phase 01 — Initialization              (required for M+)          ─┐
              ↓                                                    │
Phase 02 — Prerequisite Tasks          (optional, LLM judges)      │ Phase A
Phase 03 — Algorithm Design            (optional, LLM judges)      │ 需求构建阶段
              ↓                                                    │
Phase 04 — Implementation Plan         (required for M+)           │
              ↓                                                    │
Phase 05 — Task Planning               (required for M+)           │
              ↓                                                    │
Phase 06 — Create start-and-resume.md  (required for M+)          ─┘
              │
═══════════════════════════════════════════════════════
▲  Phase A → B GATE — USER CONFIRMATION REQUIRED    │
│  Agent submits: doc summary + execution mode       │
│  User confirms → Agent creates branch → enters B   │
═══════════════════════════════════════════════════════
              │
              ▼
Phase 07 — Execution                   (required for M+)          ─┐
              │                                                    │ Phase B
              ▼                                                    │ 需求执行阶段
     Round Review                      (check issues.md)          ─┘
         │
    ┌────┴────────┐
    │             │
  open          no open
  issues        issues
    │             │
    ▼             ▼
 Phase 01*     ✅ Done
 (Round N+1)
    │
    └──→ back to Phase A (Phase 01-06)
         (next round)
```

Phases 02 and 03 are **independent** (parallel, not sequential) — both, one, or neither may be needed.

## Phase Reference

**Phase A — 需求构建阶段**

| Phase | Output | Reference |
|---|---|---|
| Blueprint layer | `.dev/blueprint.md` | [shared/05-blueprint-management.md](shared/05-blueprint-management.md) |
| 01 Initialization | `init.md` | [phase-a/00-initialization.md](phase-a/00-initialization.md) |
| 02 Prerequisite Tasks | `inspect.md` / `research.md` / `profiling.md` / `diagnosis.md` | [phase-a/01-prerequisite-tasks.md](phase-a/01-prerequisite-tasks.md) |
| 03 Algorithm Design | `algorithm-design.md` | [phase-a/02-algorithm-design.md](phase-a/02-algorithm-design.md) |
| 04 Implementation Plan | `plan.md` | [phase-a/03-implementation-plan.md](phase-a/03-implementation-plan.md) |
| 05 Task Planning | `tasks.md` | [phase-a/04-task-planning.md](phase-a/04-task-planning.md) |
| 06 Create start-and-resume.md | `start-and-resume.md` | [phase-b/00-start-and-resume.md](phase-b/00-start-and-resume.md) § Step 0 |

**Phase A→B Gate — 用户确认门** (see Step 6b above)

**Phase B — 需求执行阶段**

| Phase | Output | Reference |
|---|---|---|
| 07 Execution | code | [phase-b/00-start-and-resume.md](phase-b/00-start-and-resume.md) |
| Round Review | `issues.md` + Round History + N+1 loop | [phase-b/01-round-mechanism.md](phase-b/01-round-mechanism.md) |

> **Blueprint**: `.dev/blueprint.md` tracks all requirements, phases, and dependencies. Updated at every phase transition. See [shared/05-blueprint-management.md](shared/05-blueprint-management.md).

## Coding Reference

| Topic | Reference |
|---|---|
| OOP & SOLID Principles | [shared/01-oop-principles.md](shared/01-oop-principles.md) |
| Coding Standards (all languages) | [shared/02-coding-standards.md](shared/02-coding-standards.md) |
| Git Workflow | [shared/03-git-workflow.md](shared/03-git-workflow.md) |
| Round Mechanism | [phase-b/01-round-mechanism.md](phase-b/01-round-mechanism.md) |
| Reader's Guide | [references/README.md](references/README.md) |

## Utility Scripts

Scripts under `scripts/` provide deterministic checks for common workflow tasks:

| Script | When to Use | What It Checks |
|--------|-------------|----------------|
| [validate-branch.sh](scripts/validate-branch.sh) | Entering execution loop, or any time before committing | Branch naming, not on main, .dev/ exists, uncommitted changes |
| [check-dev-structure.sh](scripts/check-dev-structure.sh) | When resuming project, or verifying project health | .dev/ blueprint, requirement docs, round artifacts |
| [check-phase-b-prereqs.sh](scripts/check-phase-b-prereqs.sh) | After Phase A→B Gate confirmation, before Phase 07 | Branch exists, core docs present, latest round has plan+tasks |

All scripts are read-only — run with `bash scripts/<name>.sh [args]`.

## Methods

| Method | Phase | When to Use | Reference |
|--------|-------|-------------|-----------|
| Term Grilling + ADR | 01 / 02 / 04 | Fuzzy terminology, hard-to-reverse decisions | [methods/00-term-grilling-and-adr.md](methods/00-term-grilling-and-adr.md) |
| Vertical Slice TDD | 07 | Tasks with clear public interfaces | [methods/01-vertical-slice-tdd.md](methods/01-vertical-slice-tdd.md) |
| Dual-Axis Review | Round Complete / PR | Significant code reviews | [methods/02-dual-axis-review.md](methods/02-dual-axis-review.md) |
| Architecture Deepening | 02 | Modifying code with shallow modules | [methods/03-architecture-deepening.md](methods/03-architecture-deepening.md) |
| Structured Debugging | 02 | Non-trivial bug fixes | [methods/04-structured-debugging.md](methods/04-structured-debugging.md) |

### Method Selection — Trigger-Driven

Methods are gate-checked by trigger conditions, not optional suggestions. At each phase entry, the agent **MUST**:

1. Identify all methods tagged for that phase (see the table above)
2. Read each method's `## When to Use` / `## Do Not Use` sections from its standalone file
3. Evaluate trigger conditions against current context
4. Apply if triggers match; produce a specific factual justification if they do not

The Method Selection table is produced as a planning artifact at every applicable phase entry. Skipping without justification is not permitted. The trigger conditions are defined in each method's documentation — the phase docs do not duplicate them.

## Core Rules

Rules unique to this skill. See `00-agent-execution.md` for: `§ File Reading Discipline` (read before edit), `§ Self-Check` (tests/quality), `§ Phase Transition Re-read Discipline` (always re-read phase doc before starting), `§ Round-based Execution Model` (issues.md gating), `§ Design Principle Compliance` (OOP/SOLID).

- Minimize changes when project `live`; breaking changes OK for `pre-launch` + new modules
- All identifiers, comments, docs in English
- **Maintain the blueprint** — update `.dev/blueprint.md` at every phase transition
- **Start with references/README.md** — reader's guide before diving into phase docs
- **Run Method Selection at every phase entry** — evaluate tagged methods against trigger conditions. Apply if triggers match; justify if they don't.
- **⚠ Follow the Deviation Protocol** — when implementation differs from plan.md: stop, assess severity, log to `issues.md`, present options to user. **Never silently modify plan.md, add unplanned files, or change interfaces without logging the deviation.** See `phase-b/00-start-and-resume.md § Deviation Protocol`.
- **Phase B Execution Discipline applies** — see [phase-b/00-start-and-resume.md § Phase B Execution Discipline](phase-b/00-start-and-resume.md#phase-b-execution-discipline). All Phase B agents MUST read start-and-resume.md + SKILL.md before execution. No implicit fallback.
