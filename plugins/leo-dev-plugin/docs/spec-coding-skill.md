# spec-coding-skill

> **Version:** 2.1
>
> A spec-driven methodology for LLM agents to define, plan, and implement coding work with quality and consistency. Uses a **two-phase model** (Requirements Construction → Execution) connected by a **hard user-confirmation gate**, with **round-based iterative execution** for handling deviations.

## Workflow

```
Task Sizing (XS → direct, S → light, M+ → full phases)
     │
     ▼
┌─────────────────────────────────────────────────┐
│            Phase A — Requirements Construction   │
│                                                 │
│  Phase 01 — Initialization         (init.md)    │
│       ↓                                        │
│  Phase 02 — Prerequisite Tasks    (opt)         │
│  Phase 03 — Algorithm Design      (opt)         │
│       ↓                                        │
│  Phase 04 — Implementation Plan   (plan.md)     │
│       ↓                                        │
│  Phase 05 — Task Planning         (tasks.md)    │
│       ↓                                        │
│  Phase 06 — Create start-and-resume.md          │
└──────────────────────┬──────────────────────────┘
                       │
═══════════════════════╪═══════════════════════════
        ▲ A→B GATE — USER CONFIRMATION            │
        │ 1. Agent submits: docs + branch name    │
        │ 2. User confirms → branch created       │
═══════════════════════╪═══════════════════════════
                       │
                       ▼
┌─────────────────────────────────────────────────┐
│          Phase B — Execution Phase               │
│                                                 │
│  Phase 06.5 — Execution Planning                │
│    ├── Scan agent types                         │
│    ├── Draft execution-plan.md                  │
│    └── User confirms execution plan             │
│       ↓                                        │
│  Phase 07 — Execution Loop  (12-step 0-11)      │
│    ├── Per-task: read → impl → test → commit    │
│    ├── Deviation check after every step         │
│    └── Batch limit: 3 tasks → review checkpoint │
│       ↓                                        │
│  Round Review → issues? → Round N+1 → Done     │
└─────────────────────────────────────────────────┘
```

## Task Sizing

| Size | When | Ceremony |
|------|------|----------|
| XS | 1 file, trivial change | Brief init.md + inline plan → implement → test → commit |
| S | 1-3 files, well-defined | Light init.md (Spec + Requirements + Plan) → implement → test → commit |
| M | Multi-module feature | Full Phase A→B flow (Phase 01-07) |
| L/XL | Cross-requirement | Full flow + Blueprint + Phase 02 mandatory; re-evaluate size after Phase 02 |

## Key Concepts

### Phase A → B Gate

After Phase A (requirements docs) completes, the agent presents a summary with branch name and execution mode preview. **The agent cannot enter Phase B until the user explicitly confirms.** On confirmation, the branch is created automatically.

### Phase 06.5 Execution Planning

A mandatory planning phase after the gate and before execution. Scans available agent types, drafts `execution-plan.md` with full sub-agent startup prompts, and presents for user confirmation. Sub-agents read the **Phase B Agent Brief** (`references/phase-b-agent-brief.md`) — a condensed ~150-line summary — instead of loading all 7 reference documents at once.

### 12-Step Execution Loop

The core of Phase 07. Each task follows steps 0-11 continuously: confirm branch → read docs → implement → deviation check → verify → test → commit. Deviation Protocol handles plan-reality mismatches at Low/Medium/High severity. Detailed in `phase-b/02-execution-loop.md`.

### Round-Based Execution

Problems found during a round are logged to `issues.md` and resolved in the next round (Round N+1), not silently fixed mid-flight. Previous round artifacts are preserved as historical records under `generated/rounds/round-NNN/`. Round N+1 re-enters Phase A (Phase 01*) incrementally.

### Method Selection

Five trigger-driven methods (TDD, Structured Debugging, Architecture Deepening, Term Grilling + ADR, Dual-Axis Review) are evaluated at every phase entry. Methods are **not advisory** — if trigger conditions match, they **must** be applied. Skip justifications must cite concrete artifacts, not generic "not needed." See `references/trigger-index.md` for the full aggregation.

## Best Practices

### 1. Always let task sizing run first

Even if the request seems simple, let the skill determine the size. It catches edge cases where "simple" changes have far-reaching effects.

### 2. Follow the Phase Transition Re-read Discipline

Before entering any phase, the agent **must** re-read that phase's reference file. This is not optional — it prevents the agent from operating on stale context.

### 3. Use methods when triggers match

Methods like TDD, Structured Debugging, and Dual-Axis Review have explicit trigger conditions. If they match, apply them. "Not needed" without justification is invalid.

### 4. Never silently deviate from plan.md

If implementation reveals something different from the plan, stop and log a deviation. See the Deviation Protocol in `phase-b/02-execution-loop.md`.

### 5. Keep the blueprint up to date

`.dev/blueprint.md` tracks all requirements across rounds. Update it at every phase transition.

### 6. Round history matters

Each round builds on the previous one. `issues.md` drives the N+1 loop — don't skip it.

### 7. Sub-agents start with the Phase B Agent Brief

Sub-agents entering Phase B should read `references/phase-b-agent-brief.md` first — it condenses all mandatory rules into ~150 lines. Full reference documents (`shared/00-agent-execution.md`, `shared/02-coding-standards.md`, etc.) are available on-demand when detailed context is needed.

### 8. Execution agents are limited to 3 consecutive tasks

To maintain quality, execution agents run at most 3 tasks before a review checkpoint. Fewer than 3 total tasks? The limit does not apply.

## Files Generated

```
.dev/
├── blueprint.md                         ← Cross-requirement roadmap
├── TODO.md                              ← Cross-requirement backlog
├── CONTEXT.md                           ← Project glossary (Term Grilling)
├── <NNN>-<req-name>/
│   ├── init.md                          ← Spec + Requirements + Action Items + Constitution
│   ├── issues.md                        ← Cross-round issue tracker
│   ├── generated/
│   │   ├── start-and-resume.md          ← Session bootstrap & round guide
│   │   └── rounds/
│   │       └── round-NNN/
│   │           ├── plan.md              ← Implementation plan
│   │           ├── tasks.md             ← Task breakdown (status: not-started/in-progress/done/blocked)
│   │           ├── execution-plan.md    ← Sub-agent setup & prompts (Phase 06.5)
│   │           └── issues.md            ← Per-round issue snapshot
```

## Reference Architecture

| Area | File(s) |
|------|---------|
| Agent rules (read first) | `shared/00-agent-execution.md` |
| Phase B Agent Brief (sub-agents) | `references/phase-b-agent-brief.md` |
| OOP & SOLID | `shared/01-oop-principles.md` |
| Coding standards | `shared/02-coding-standards.md` |
| Git workflow | `shared/03-git-workflow.md` |
| Blueprint management | `shared/05-blueprint-management.md` |
| Phase A phases (01–06) | `phase-a/00-initialization.md` ~ `04-task-planning.md` |
| Phase A→B Gate + Phase 06.5 | `phase-b/00-start-and-resume.md` § Part 2-3 |
| Execution loop + Deviation Protocol | `phase-b/02-execution-loop.md` |
| Round state machine | `phase-b/01-round-mechanism.md` |
| Trigger index (all methods) | `references/trigger-index.md` |
| User interaction (language, mode) | `references/user-interaction.md` |
| Project overview queries | `references/project-overview-query.md` |

## Method Reference

| Method | Phase | When |
|--------|-------|------|
| Term Grilling + ADR | 01 / 02 / 04 | Fuzzy terms, hard decisions |
| Vertical Slice TDD | 07 | Clear public interfaces |
| Dual-Axis Review | Round end / PR | Significant code review (>5 tasks or >10 files) |
| Architecture Deepening | 02 | Shallow modules, unclear boundaries |
| Structured Debugging | 02 | Non-trivial bugs, non-deterministic repro |

## Validation Scripts

| Script | Purpose |
|--------|---------|
| `scripts/validate-branch.sh` | Check branch naming, not on main, uncommitted changes |
| `scripts/check-dev-structure.sh [path]` | Validate .dev/ documentation tree (accepts optional path arg) |
| `scripts/check-phase-b-prereqs.sh <req>` | Verify branch + core docs before Phase 07 entry |
