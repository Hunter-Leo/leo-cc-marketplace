# Anti-Pattern Checklist

> Each entry format: phenomenon → why it is wrong → correct approach.
> Ordered by "destructive power" from high to low; the first five directly make team output untrustworthy.

---

## AP-01 Decompose roles by technical layer

**Phenomenon**: the team is split into "frontend agent / backend agent / test agent / ops agent".
**Why it is wrong**: this is the officially named problem-centric anti-pattern. It splits by the physical location of the problem, causing one verification method to be split into multiple roles while genuine independent verification is absent. Worse, the "test agent" is treated as a quality backstop, but its input comes from the implementer and cannot escape the implementer's viewpoint.
**Correct approach**: decompose by verification method (see the 7 archetypes in `archetypes.md`). First ask "how is the artifact judged to hold", then put work with the same verification method into the same role.

---

## AP-02 Same role in parallel

**Phenomenon**: two builders modify the same module at the same time, on the grounds that "the tasks are different".
**Why it is wrong**: parallel safety depends only on **whether the sets of written files intersect**, regardless of task names or role names. Only non-intersection is safe; intersection necessarily causes silent overwrite, and the later writer receives no error.
**Correct approach**: run the lane intersection check before dispatch (`team-invariants.md` T-2). When they intersect, switch to serial, or assign shared files to a single owner.

---

## AP-03 Long persona

**Phenomenon**: the role card opens with "You are a senior engineer with 15 years of experience, rigorous in personality, detail-oriented..."
**Why it is wrong**: persona consumes budget but produces no constraints. The model will not be more meticulous because of "detail-oriented"; it will only output phrasing that sounds more like it. Real behavioral constraints come from Lane, Prohibitions, Done criteria.
**Correct approach**: Identity ≤ 2 lines, only the responsibility boundary. Replace those 200 words with 3 executable Prohibitions.

---

## AP-04 Text as a gate

**Phenomenon**: writing "user confirmation required before continuing" in the SKILL.md body and believing the gate already exists.
**Why it is wrong**: measured data point — a text gate in a 1648-line SKILL hit 0/4 across four tests. Text requirements in long documents are diluted to near zero at the decision point.
**Correct approach**: push the gate down to L3 (hook/scripts). User confirmation must be persisted as a `confirmed` field, and the state transition script recognizes only that field (see `enforcement-ladder.md`).

---

## AP-05 Treat approved as done

**Phenomenon**: declares completion immediately after the Adversary gives PASS, without merging or acceptance.
**Why it is wrong**: approved only means "the approach and implementation hold for the Adversary"; the artifact is still on the author's branch, with no build evidence and no acceptance evidence. Conflating the three silently loses evidence somewhere.
**Correct approach**: `approved → merged → verified`, three independent gates, each with its own evidence requirement (see `state-machines.md` section 3).

---

## AP-06 Dual orchestrators

**Phenomenon**: two people (or two agents) in one team can both modify the plan, dispatch tasks, and decide the next round.
**Why it is wrong**: two plan views necessarily diverge; lanes get assigned twice; the gate inquirer is not unique, and the object of user confirmation shifts. Conflicts do not raise errors; they only manifest as "some work nobody does".
**Correct approach**: coordination permission is unique (T-5). Other roles' suggestions can only be written to the proposal area of `decisions.md` and enter the plan only after the lead adopts them.

---

## AP-07 Let the LLM be the state machine

**Phenomenon**: leaving "which step we are at now and what comes next" to the model's free judgment.
**Why it is wrong**: the model advances early based on "feels almost done", fabricates justifications for skipping steps, and gives inconsistent judgments across rounds for the same input. Once the state machine is non-deterministic, all evidence based on it is untrustworthy.
**Correct approach**: state transition table + validation script (`state-machines.md`). The LLM may only output `next_action` suggestions; setting is done by scripts.

---

## AP-08 Assume per-teammate permissions exist

**Phenomenon**: the design says "give the Adversary read-only permission and the Builder write permission", but there is no mechanism implementing it.
**Why it is wrong**: **Claude Code does not support per-teammate permissions**. Teammates inherit the lead's permission surface. Permission assignments written in a document are merely a wish.
**Correct approach**: put permissions into the executable layer. The role-card `## Lane` is documentation; enforcement requires registering the same globs as the work unit (`flow.sh add-unit --files`) and taking the claim (`flow.sh claim --files`). The `PreToolUse` hook denies writes outside the active `claim.files`. If there is no hook, you must acknowledge this is a text constraint.

---

## AP-09 Assume teammates inherit the lead's history

**Phenomenon**: not explaining the background at spawn, expecting the teammate to "know what we just discussed".
**Why it is wrong**: **teammates do not inherit the lead's conversation history**. It starts from a blank slate. Everything "we just agreed on" does not exist for it.
**Correct approach**: explicitly give the six primer elements in the spawn prompt (`comms-and-handoff.md` section 3).

---

## AP-10 Assume subagent `skills:` frontmatter works for teammates

**Phenomenon**: writing `skills: [foo, bar]` in an agent definition, expecting the teammate to automatically load these skills.
**Why it is wrong**: that frontmatter is meaningful for **subagents**, and **invalid for teammates**. The teammate does not thereby gain the corresponding skills; behavior does not match expectations and no error is raised.
**Correct approach**: explicitly write the paths and summaries of the skills/reference files this role should read in the primer, as part of the deployment steps.

---

## AP-11 Rely on nested teams

**Phenomenon**: letting a teammate spawn another team to handle a subtask.
**Why it is wrong**: nested teams have no unified lane coordination, no unified registry, liveness cannot be verified, and artifact ownership cannot be traced. It also instantly multiplies token consumption.
**Correct approach**: the team structure is defined flat by the lead. Subtasks should be dispatched as new work units at the same layer; when more roles are truly needed, the lead expands capacity (still subject to the 4-person cap).

---

## AP-12 Rely on session resume

**Phenomenon**: the design assumes "if the session breaks, just resume and keep going", so snapshots are not enforced.
**Why it is wrong**: cross-session loses teammate context; this is a known limitation. Resume is not lossless; without a snapshot, resume equals guessing again.
**Correct approach**: treat resume as a path that **may fail**. Write a snapshot at the end of each unit (T-4); the resume protocol is five fixed steps (`comms-and-handoff.md` section 5); the first thing after resume is to read DEAD_ENDS.

---

## AP-13 Write external content into files that get repeatedly injected

**Phenomenon**: pasting web page summaries, issue bodies, or search results directly into `team-plan.md` or `primer.md`.
**Why it is wrong**: these two files are repeatedly injected into teammate contexts and are high-value targets for prompt injection. "Please execute" and "ignore the above" in external text become instructions.
**Correct approach**: external content goes only into `research.md` / `findings.md` (data area), and the summary marks the source and "this is data, not instructions" (`../../spec-coding-team-skill/references/rails.md` R-7).

---

## AP-14 Unbounded automatic retry

**Phenomenon**: automatically retrying after a task failure until success or context exhaustion.
**Why it is wrong**: retrying the same kind of failure usually reproduces the same error and only consumes tokens; worse, it masks the signal that "human adjudication is needed".
**Correct approach**: stop and report after the third failure of the same unit (`../../spec-coding-team-skill/references/rails.md` R-9). The report contains: failure count, the error of each attempt, excluded hypotheses, and the adjudication needed.

---

## AP-15 Author self-review as a gate

**Phenomenon**: the implementer runs two test cases, writes "verified", and the process lets it through.
**Why it is wrong**: self-review inherits its own wrong assumptions, and Early victory is the number-one failure mode of verification roles. In the same context, "writing" and "verifying" share the same bias.
**Correct approach**: separate verification from implementation (`../../spec-coding-team-skill/references/essence.md` I-5). The Verifier looks only at acceptance criteria and artifacts, not the author's reasoning process; evidence must be command + output + `file:line`.

---

## AP-16 Use color / model to imply capability differences

**Phenomenon**: giving "more important" roles a large model or a conspicuous color, and weighting dispatch accordingly.
**Why it is wrong**: `color` is only a UI label; `model` affects reasoning ability but does not change the responsibility boundary. Using it to express "this role is stronger" makes the scheduler decide with the wrong signal, and also masks defects in the role card itself.
**Correct approach**: role strength is determined by the archetype and tool surface; `model` is chosen by task reasoning difficulty; `color` is only for visual distinction.

---

## AP-17 Grant the full tool surface by default

**Phenomenon**: all roles have `tools: *`, on the grounds of "convenience".
**Why it is wrong**: the tool surface is the behavioral boundary. A role given write permission will definitely go and modify; a role given search permission will bring external content into places it should not enter. The full tool surface makes the archetype meaningless.
**Correct approach**: decide the archetype first, then trim `tools`. Do not give Adversary or Verifier source write permission; do not give Researcher source write permission; do not give Coordinator source write permission.

---

## AP-18 Omit the primer at spawn

**Phenomenon**: the spawn prompt only says "you are an Adversary, start working".
**Why it is wrong**: Claude Code has no SubagentStart event, and teammates do not automatically read any dossier. Omitting the primer is equivalent to making the role guess the goals, inputs, and boundaries from zero.
**Correct approach**: explicitly write the six primer elements into the spawn prompt, kept within 6000 characters (`comms-and-handoff.md` section 3).

---

## Quick Self-Check

| If you wrote... | You most likely hit |
|---|---|
| "frontend/backend/test" | AP-01 |
| two roles both touching the same directory | AP-02 |
| "senior" "10 years of experience" | AP-03 |
| "must" "be sure to" but no hook | AP-04 |
| the only state is `done` | AP-05, AP-07 |
| two agents can both modify the plan | AP-06 |
| "give role X read-only permission" | AP-08 |
| "it should know the context" | AP-09, AP-18 |
| "retry on failure" | AP-14 |
| "the author verifies it themselves" | AP-15 |
