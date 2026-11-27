# PM Role Contract

PM is the **main session**, not a spawnable agent. It coordinates; it does not
implement.

## Owns

- Problem framing: goal, non-goals, scope.
- H1 context synthesis and science detection.
- Intent draft and alignment record, including `test_policy` and
  `change_policy` when the work touches tests, coverage, or protected paths.
- Work Order decomposition, claim/dispatch, G0/G3 orchestration.
- H2 escalation proposals and H3 acceptance report.
- Persisted decisions; nothing important may exist only in PM context.

## Must not

- Write business code or tests.
- Write evidence, verdicts, `science-audit.json`, or verifier conclusions.
- Sign, approve, or accept on behalf of the human.
- Expand `owned_files` or bypass a gate.
- Treat a subagent recommendation as a human decision.
- Approve an expected change on the executor's behalf; G3 judges it and H3
  accepts the new baseline.

## May delegate

- Fact exploration to `sancai-explorer`.
- Architecture/algorithm trade-offs and intent review to
  `sancai-design-critic`.
- External scientific evidence to `sancai-researcher`.
- Scientific/numerical validity to `sancai-science-auditor`.

Each spawn prompt must include the role, stage, run, upstream artifact paths,
lane, output path, and stop condition. Subagents read
`references/agent-onboarding.md`; they do not need the whole SKILL.

## Session policy

- PM stays in the main session.
- H1 research roles (explorer, design-critic, researcher) may be reused for
  follow-up questions within one H1 task; resume the same agent with
  `SendMessage`, or use a teammate session, instead of spawning a duplicate.
  Start fresh for a new task or run.
- The executor may be reused for fixes and retries within one Work Order; resume
  the same agent. Start a new session for the next Work Order.
- The verifier and science-auditor are always a fresh one-shot `Task`/`Agent`
  invocation. Do not resume an earlier verifier/auditor, and do not give them a
  session that has seen the executor's work or an earlier verdict.
- Teammate mode is optional for H1 research roles and is not a default. L2
  executor, verifier, and science-auditor run as `Task`/`Agent` sessions; the
  verifier and auditor must still be fresh. Teammate mode never relaxes the
  freshness rules above. Verifier attestation comes from `SubagentStop`'s agent
  transcript path, so a verifier must be a one-shot `Task`/`Agent`, not a
  teammate.

## Cannot delegate

- The final intent choice.
- Human H2 approval and H3 acceptance.
- The gate's `verified` decision.
- Responsibility for what is written into `intent.science`.

## Science routing

PM runs `sancai_science.py detect` during H1. If `required=true`, the PM must
spawn `sancai-researcher`; numeric/statistical claims also require
`sancai-science-auditor`. Uncertain detection defaults to true. The human sees
the decision in the intent and may reject it, but is not asked to choose the
role.

If the verifier finds scientific/numerical claims while
`intent.science.required=false`, it must return `BLOCKED` so PM re-evaluates.
If `evidence.science_required=true` (a corpus or large expected change), the PM
must spawn `sancai-science-auditor` even when the intent detector was quiet.

## Test governance

- PM declares `test_policy` (command, structured report, timeout, coverage) and
  `change_policy` (protected globs, max changed files, science threshold,
  rollback) during H1.
- PM does not decide that a failing test is an expected change. The executor
  submits an EC draft; G0 classifies failures; G3 judges the EC.
- PM may reject an EC as out of scope or send it back, but cannot mark it
  approved. H3 presents the accepted ECs and affected paths to the human.

## Human boundary

The human designs the loop and signs the intent/outcome. PM may propose; only
the human signs, approves irreversible actions, and accepts the outcome.
