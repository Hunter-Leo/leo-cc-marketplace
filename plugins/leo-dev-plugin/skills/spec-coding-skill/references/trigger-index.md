# Trigger Index — Method Selection Triggers by Phase

> Aggregated trigger conditions for all methods across all phases. Read the referenced method file for full "When to Use" / "Do Not Use" details.

## Phase 01 — Initialization

| Method | Trigger Signals | Reference |
|--------|----------------|-----------|
| Term Grilling + ADR | Fuzzy terminology ("robust", "scalable", "efficient", undefined concepts), hard-to-reverse decisions (tech stack, data model, interface contracts) | [methods/00-term-grilling-and-adr.md](methods/00-term-grilling-and-adr.md) |

## Phase 02 — Prerequisite Tasks

| Method | Trigger Signals | Reference |
|--------|----------------|-----------|
| Architecture Deepening | Modifying existing code with shallow modules; unclear module boundaries; monolith extraction needed | [methods/03-architecture-deepening.md](methods/03-architecture-deepening.md) |
| Structured Debugging | Non-trivial bug fix; non-deterministic repro; root cause not visible from error message | [methods/04-structured-debugging.md](methods/04-structured-debugging.md) |
| Term Grilling + ADR | ADRs needed for decisions in prerequisite docs (e.g., choosing between libraries, architectures) | [methods/00-term-grilling-and-adr.md](methods/00-term-grilling-and-adr.md) |

## Phase 04 — Implementation Plan

| Method | Trigger Signals | Reference |
|--------|----------------|-----------|
| Term Grilling + ADR | Plan stress test needed; hard-to-reverse plan decisions (e.g., data flow, module boundaries) | [methods/00-term-grilling-and-adr.md](methods/00-term-grilling-and-adr.md) |

## Phase 07 — Execution (per-task)

| Method | Trigger Signals | Reference |
|--------|----------------|-----------|
| Vertical Slice TDD | Task has a clear, stable public interface; behavior can be tested in isolation | [methods/01-vertical-slice-tdd.md](methods/01-vertical-slice-tdd.md) |

## Round Complete

| Method | Trigger Signals | Reference |
|--------|----------------|-----------|
| Dual-Axis Review | Significant round with substantial new code (>5 tasks, >10 files changed, or cross-module dependencies touched) | [methods/02-dual-axis-review.md](methods/02-dual-axis-review.md) |

---

## Evaluation Requirement

At EVERY phase entry, ALL methods tagged for that phase must be evaluated:
1. Read `## When to Use` / `## Do Not Use` from the method file
2. Check trigger conditions against current context
3. Apply if triggers match; produce a specific factual justification if they do not
4. Generic "Not needed" is invalid — cite concrete artifacts
