---
name: agent-team-authoring
description: "This skill should be used when the user asks to design an agent team, write a multi-agent workflow, split roles, decide whether to form a team, or choose which enforcement layer to use, because it answers only whether to form a team, how to split it, how to write each role card, and where to place constraints, and it should not be used when the user merely wants one specific piece of work completed rather than a team design."
---

# Agent Team Authoring

Writing a team is not writing roles. If the roles are well written but the team structure is wrong, the result is four agents each correctly doing the wrong thing.

This skill outputs only "design"; it does not produce the business artifacts of the designed team. It shares the same underlying source of truth with the spec-coding family: the six invariants are in `../spec-coding-team-skill/references/essence.md`, and the all-hands discipline is in `../spec-coding-team-skill/references/rails.md`. This skill does not redefine them.

## 1. Three Questions Before Writing a Team

Every team request must first pass the three questions, producing one of three verdicts. **You must write the reason**; a verdict without a reason counts as incomplete.

| # | Question | Basis for "yes" | Result if "no" |
|---|---|---|---|
| Q1 | **Independence**: Can this work be split into mutually independent, separately verifiable units? | Each unit has its own acceptance criteria, and failures do not infect each other | `single_session` |
| Q2 | **Conflict of viewpoints**: Are there decisions that need to be genuinely challenged, rather than labor that can be completed in parallel? | There is at least one judgment whose "conclusion may be overturned" (technology choice, approach, completeness) | `workflow` |
| Q3 | **Is it worth splitting**: Is the coordination cost less than the loss of "one context cannot hold it"? | A single context cannot accommodate all inputs + artifacts + verification | `workflow` |

The output format is fixed to one line:

```
Conclusion: agent_teams | workflow | single_session — reason: <one sentence, pointing to which question decided it>
```

Meanings of the three outputs:

- `single_session` — one agent completes it sequentially. No team, no mailbox, no role cards.
- `workflow` — a single agent + explicit phases and artifacts, chained by scripts or a sequential process. No added parallelism, no adversary role.
- `agent_teams` — multiple agents in parallel, including at least one role that **does not serve implementation** (adversary / verification / research).

## 2. Four Trigger Conditions

Only when any condition is met is a team worth forming; if none is met, fall back to `workflow`. This prevents "forming a team for the sake of using a team".

| Trigger condition | Criterion | What happens if missing |
|---|---|---|
| **One context cannot hold it** | inputs + artifacts + verification evidence exceed a single context budget | later work can only rely on memory, silently losing constraints |
| **Genuinely different tool surfaces and behavioral constraints are needed** | two roles' writable paths, available tools, and prohibitions must differ | "multiple roles" written under the same set of constraints are just the same viewpoint repeated |
| **Parallelizable and wall-clock matters** | no write conflicts between units, and total duration is the goal | parallelism only adds coordination cost, it does not reduce time |
| **An uncontaminated second opinion is needed** | someone who has not seen the implementation reasoning process is needed to judge | self-review inherits its own wrong assumptions; review becomes confirmation bias |

Note the last one: the value of a second opinion comes from being "uncontaminated", not from "one more agent". Letting the Adversary read the author's reasoning process is contamination.

## 3. Decompose Roles by Verification Method

**Do not decompose by technical layer** (frontend / backend / test / ops). This is the officially named problem-centric anti-pattern: it splits by "what the problem looks like", not by "how the artifact is verified".

The correct way: first ask "by what means is this role's artifact judged to hold?" — only work with the same verification method belongs to the same archetype.

| archetype | One-line criterion | Typical artifacts | Core tool surface |
|---|---|---|---|
| Coordinator | does not change artifacts itself; only splits, schedules, adjudicates | plan, task table, adjudication record | plan files + SendMessage |
| Builder | the artifact is executable, and "it runs" is the acceptance condition | code, scripts, runnable config | write source + execute |
| Adversary | has veto power; a veto must come with evidence | findings (with severity) | read-only + execute + write findings |
| Researcher | every conclusion comes with a verifiable source | research.md | search/fetch + write research |
| Explainer | explains the system as an inspectable structure | architecture notes, tradeoff table | read-only + write architecture docs |
| Contract Designer | extracts reusable contracts that downstream can implement against | schema, interface contract, template | read/write spec paths |
| Verifier | judges only by acceptance criteria, ignoring the author's reasoning | acceptance report (with command and output) | execute + read-only + write verification |

Hard rule: **a role can belong to only one archetype**. For full definitions, failure modes and counterexamples see `references/archetypes.md`.

## 4. The 11 Role Card Fields

Each role is written as one card. A missing field = the role is invalid, not "to be added later".

| # | Field | One-line requirement |
|---|---|---|
| 1 | Identity | One sentence: who you are, what you are responsible for. ≤ 2 lines, no résumé |
| 2 | Lane | Writable path glob list + read-only path list |
| 3 | Inputs | Upstream artifact paths + output BLOCKED when missing |
| 4 | Procedure | 5–9 ordered steps, each observable |
| 5 | Prohibitions | 3–7 explicit prohibitions |
| 6 | Output contract | Persisted path + fixed return format |
| 7 | Done criteria | Executable commands or thresholds, not adjectives |
| 8 | Escalation | When to stop, whom to report to, what to report |
| 9 | Rails | Write only "see `../spec-coding-team-skill/references/rails.md`", do not copy |
| 10 | Context budget | File read size cap and sharding strategy |
| 11 | Anti-patterns | 3–5 failure modes specific to this role |

See `references/role-card-schema.md` for field definitions, counterexamples and length guidance; see `templates/role-card.md` for a copyable template.

## 5. Three Layers of Enforcement

The same rule, written at different layers, differs in actual binding force by an order of magnitude.

| Layer | Guarantees | Does not guarantee | Cost |
|---|---|---|---|
| **Text rules** | the reader will know once they read it | it will be executed | extremely low |
| **Document structure** | fields exist, missing ones are visible | semantic correctness | low |
| **hook / scripts** | violation fails | the intent is reasonable | high (must write and maintain code) |

Community data point: a gate written as a text requirement in a 1648-line SKILL hit **0/4** in four trigger tests. Text gates get diluted to near zero in long documents. This is not a matter of "not writing it prominently enough"; it is choosing the wrong layer.

See `references/enforcement-ladder.md` for the decision table and the layer-selection method.

## 6. Five Team-Level Invariants

These five differ from the six in `../spec-coding-team-skill/references/essence.md`: the six govern the **process**, the five govern **team runtime**. See `references/team-invariants.md` for per-rule details, consequences of violation and mechanical checks.

| # | Invariant | One sentence |
|---|---|---|
| T-1 | files over context | no persisted file = it never happened |
| T-2 | own your files | write only paths within your own Lane |
| T-3 | liveness is receipt | only a SendMessage receipt from this session counts as "alive" |
| T-4 | keep checkpoint | a snapshot must be left at the end of every unit |
| T-5 | lead coordinates | team-level decisions can only be made by the lead |

## 7. Scale Guidance

| Scale | Applies to | Notes |
|---|---|---|
| **2–3** | default | one implementation + one Adversary or one Verifier, or add a Coordinator |
| **4** | maximum | add only when a third verification method appears |
| 5+ | stop | first question the decomposition, then consider adding people |

**Coordinators do not count toward scale.** A coordinator produces no business artifacts; its existence is to make others wait on each other less.

A multi-agent setup consumes 3–10× more tokens than a single agent (official data). Before adding each role, first answer "which self-review does it replace?"

## 8. Reference Map

| File | Read when |
|---|---|
| `references/anti-patterns.md` | checking a draft design against known failure modes before delivery |
| `references/archetypes.md` | assigning each role to exactly one of the seven archetypes |
| `references/comms-and-handoff.md` | writing the return contract, the spawn primer, or the resume protocol |
| `references/enforcement-ladder.md` | deciding whether a rule belongs at L1 text, L2 structure, or L3 hook |
| `references/role-card-schema.md` | writing or reviewing an individual role card |
| `references/state-machines.md` | wiring mission and work-unit transitions into `flow.sh` |
| `references/team-invariants.md` | checking the five team-runtime invariants and their mechanical checks |
| `templates/primer.md` | preparing the ≤ 6000-character spawn dossier |
| `templates/role-card.md` | starting a new role card from a copyable skeleton |
| `checklists/authoring-checklist.md` | running the final 12-item gate before spawn |

## 9. Pre-Delivery Self-Check

After writing the team design, walk through `checklists/authoring-checklist.md` item by item. If any of the 12 items cannot produce **verifiable evidence**, the design is not complete — "considered it" is not evidence.
