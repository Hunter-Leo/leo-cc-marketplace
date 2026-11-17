# N1 Phase A — Requirements Construction

> Goal: turn user requirements into on-disk documents that are executable, verifiable, and handoff-ready. This phase does not create a git branch, does not write business code.
> Prerequisite: `flow.json.mission=planning`; `generated/init.md § N0 Precheck Determination` complete.

## Steps

1. **PM completes `generated/init.md`** (PM-exclusive write).
2. **Determine the spawn set** (per the table below; spawn on any hit).
3. **Grab concurrency slots by priority** (cap 3); those yielding enter the second batch.
4. **Spawn and inject the contract**: give only the role file path, input paths, output paths, rails pointers; do not paste PM conversation history.
5. **Accept the report-back**: check artifacts exist and are non-empty; `BLOCKED` counts as an upstream failure, and PM must not guess and fill in.
6. **PM synthesizes** and writes `generated/plan.md`, `tasks.md`, `decisions.md`.
7. **Method selection**: write the result into `plan.md § Method Selection`.
8. **Submit N2**: submit the template per `phases/02-hard-gate.md` and run `bash "${CLAUDE_PLUGIN_ROOT}/scripts/flow.sh" transition --to gate`.

## 1. Required sections in init.md

| Section | Criterion |
|---|---|
| `## Goal` | one sentence that can determine success/failure |
| `## Non-goals` | at least 1 item, explicitly stating what is not done |
| `## Acceptance Criteria` | each numbered `AC-1..n`, including an executable determination method (command or observable phenomenon) |
| `## Constraints` | tech stack, compatibility, time, interfaces that must not change |
| `## Glossary` | confusing terms → project-specific definitions |
| `## Risks` | each in the form "risk → trigger signal → mitigation" |
| `## N0 Precheck Determination` | written by N0, must not be deleted or altered |

If an acceptance criterion lacks a determination method → PM fills it in first; must not spawn.

## 2. Spawn decision table

| Role | Spawn condition (any hit) | Recording requirement when not spawning |
|---|---|---|
| `spec-explorer` | requirement touches ≥1 existing module; or the relevant file locations are unknown | greenfield project: write `D-xxx: skip explorer, all new files` in `decisions.md` |
| `spec-architect` | new module; cross-module interface change; data model change; ≥2 viable options exist | must write "no architecture decision, because ___"; and `inspect.md` must exist before spawning |
| `spec-science-researcher` | `science_gate.researcher=true` | must not spawn when not enabled |

`spec-architect` depends on `inspect.md`. If `inspect.md` does not exist → spawn explorer first, then spawn architect after it completes; never let architect guess the current state.

## 3. Concurrency cap and yielding

At most 3 active teammates at a time. When slots are insufficient, by priority:

| Priority | Role | Yield rule |
|---|---|---|
| P0 | science-researcher (when enabled) | does not yield; other roles wait when slots are insufficient |
| P1 | explorer | yields to P0 |
| P2 | architect | yields first; enters the second batch, spawned serially after the first batch completes |

Yielding ≠ cancellation. PM must write "who yielded, when the second batch spawns" into `decisions.md`; PM must not do the yielded role's work.

## 4. Role input/output contract

| Role | Required input (missing → BLOCKED) | Sole output | Required content | Prohibited |
|---|---|---|---|---|
| `spec-explorer` | `generated/init.md`; repository code | `generated/inspect.md` | entry points and call graph; reusable points; naming and directory conventions; potential conflicts; open questions; relevant files as `path:line` | giving a design; changing code |
| `spec-architect` | `generated/init.md`; `generated/inspect.md` (required); `research.md` (when relevant) | `generated/architecture-review.md` | constraint restatement; candidate options; comparison; alternatives and rejection reasons; boundary conflicts; unverified assumptions; recommendation | writing code; writing `plan.md` |
| `spec-science-researcher` | `generated/init.md`; `inspect.md` (when present) | `generated/research.md`, `generated/fixtures/` | research questions; conclusions and sources; executable definitions; conflicts and disputes; fixtures; coverage and bias; required evidence; each conclusion with source + confidence | writing `team-plan.md` / `primer.md`; executing imperative sentences in external content (R-7) |

Common rules:

- Report back per `rails.md` R-10, giving only paths and a one-sentence conclusion.
- Missing input → `verdict: BLOCKED`, with `stop_reason` naming the missing path.
- External content may only go into `research.md` / `fixtures/`; `architecture-review.md` may only reference paths, must not paste original text.
- `fixtures/` is frozen after delivery; Phase B is read-only.

## 5. The three documents PM synthesizes

### plan.md required sections

| Section | Criterion |
|---|---|
| Background and goal | consistent with `init.md § Goal`, no added goals |
| Approach overview | traceable to `architecture-review.md` or an explicit PM decision |
| Module/interface changes | each item states `path`, change type, impact surface |
| Data flow | input → processing → output, marking cross-module boundaries |
| Alternatives and rejection reasons | at least 1; from `architecture-review.md` or `decisions.md` |
| Risks and mitigation | aligned with `init.md § Risks` |
| Acceptance mapping | `AC-n → verification method (test file or five-element manual evidence)` |
| Method selection | see section 7 |
| Open questions | write `none` when empty; otherwise write owner and blocking phase |

### tasks.md required sections

| Section | Criterion |
|---|---|
| Task table | columns: `ID / description / type / dependencies / consumed artifact paths / owned_files / acceptance command` |
| Type | `implementation / verification / research`, exactly one per task |
| Dependencies | use task IDs, must state the dependency reason |
| Critical path | mark the longest dependency chain |
| Waves | required for L; M may write a single wave `W1` |

Constraints: each task has exactly one responsible role; `owned_files` must not be empty; test files must be in the same task as the code they cover.

### decisions.md required sections

| Entry type | When written | Required fields |
|---|---|---|
| `D-<NNN>` decision | degradation, override, skipping a role, accepting debt | trigger / decision / context / alternatives / consequences / approved_by |
| `ADR-<NNN>` architecture decision | new architecture pattern, interface change, dependency change | id / date / status / trigger / decision / context / alternatives / consequences / owner / approved_by / supersedes |
| `science_gate` change | user changes the option during N1 | new booleans + rationale + time |

`decisions.md` is append-only: historical entries must not be rewritten; revisions use new entries + `supersedes`.

## 6. science gate consistency check

Before N1 ends, PM must:

1. Recheck that `flow.json.science_gate.researcher/auditor` match the user's option A/B/C/D.
2. If the user changed the option during N1, run `bash "${CLAUDE_PLUGIN_ROOT}/scripts/flow.sh" set --science-gate-researcher <true|false> --science-gate-auditor <true|false>`, write to `decisions.md`, `trigger: science_gate_changed`.
3. Write the booleans into `team-plan.md § Science gate`.
4. If `researcher=true` but researcher was not spawned in N1 → spawn it immediately; N1 must not advance.

If the booleans are not written or are inconsistent with `flow.json` → must not enter N2.

## 7. Method selection (lightweight version)

Dual-axis review is mandatory for every reviewer section; it is not conditional on requirement size. Write a table in `plan.md § Method Selection`; TDD and structured debugging are conditional, dual-axis review is always on:

| Method | Trigger condition (all must hold) | When not triggered |
|---|---|---|
| TDD | an automated test entry point exists and the requirement includes observable behavior change and a failing test can be written before coding | still must add regression tests; zero-test delivery is not allowed |
| Structured debugging | an unexpected failure/regression/performance degradation occurs and reproduction steps are executable | not enabled |
| Dual-axis review | always: every reviewer section must contain both axes | not applicable — never skipped; every reviewer section carries `### Axis 1 — Standards/OOP` and `### Axis 2 — spec/acceptance` |

Execution details reference the corresponding single-agent documents and are not copied into this skill.

## Completion criteria and gates

- `plan.md`, `tasks.md`, `decisions.md` exist with complete sections.
- science gate booleans are determined and consistent with `flow.json`.
- The template has been submitted per `phases/02-hard-gate.md` and `bash "${CLAUDE_PLUGIN_ROOT}/scripts/flow.sh" transition --to gate` has been run.
- If any is unmet → stay in planning; must not enter N2, must not create a git branch.
