# init.md — [NNN]-[req-name]

## Project Stage

```
project_stage: pre-launch   # or: live
```

See `phase-b/00-start-and-resume.md § Breaking Changes Policy` for how this value affects execution.

## Spec

High-level description of the requirement:

- Background and motivation
- Core problem being solved
- Overall goal and vision
- Business value
- Usage scenarios

## Requirements

Detailed specification:

- Core objectives
- Functional requirements
- Technical requirements
- Interface or module descriptions
- Expected outputs

## Action Items

**Prerequisite documents** (if needed — see Phase 02 & 03):
- [ ] `generated/inspect.md` — existing code analysis
- [ ] `generated/research.md` — technology research
- [ ] `generated/profiling.md` — performance analysis
- [ ] `generated/diagnosis.md` — bug diagnosis
- [ ] `generated/algorithm-design.md` — algorithm design

**Round artifacts** (maintained across rounds):
- [ ] `issues.md` — Round-to-round issue log

**Required documents** (always, in order):
- [ ] `generated/rounds/round-001/plan.md` — Phase 04 (Round 1). Subsequent rounds: `round-NNN/plan.md`
- [ ] `generated/rounds/round-001/tasks.md` — Phase 05. Each round gets its own tasks.md
- [ ] `generated/start-and-resume.md` — Phase 06 (must exist before any task execution)

All generated documents go under `.dev/[NNN]-[req-name]/generated/`. Requirement-level files (`init.md`, `issues.md`) live under `.dev/[NNN]-[req-name]/`. Round-specific docs (plan, tasks, issues) live under `generated/rounds/round-NNN/`.

## Constitution

Mandatory coding standards for this requirement. See `shared/01-oop-principles.md` and `shared/02-coding-standards.md` for the full rules. Keep only the languages and rules that apply.
