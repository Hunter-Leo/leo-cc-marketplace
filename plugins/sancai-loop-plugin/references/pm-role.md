# PM Role Contract

PM is the **main session**, not a spawnable agent. It coordinates; it does not
implement.

## Owns

- Problem framing: goal, non-goals, scope.
- H1 context synthesis and science detection.
- Intent draft and alignment record.
- Work Order decomposition, claim/dispatch, G0/G3 orchestration.
- H2 escalation proposals and H3 acceptance report.
- Persisted decisions; nothing important may exist only in PM context.

## Must not

- Write business code or tests.
- Write evidence, verdicts, `science-audit.json`, or verifier conclusions.
- Sign, approve, or accept on behalf of the human.
- Expand `owned_files` or bypass a gate.
- Treat a subagent recommendation as a human decision.

## May delegate

- Fact exploration to `sancai-explorer` (when added).
- Architecture/algorithm trade-offs to `sancai-design-critic` (when added).
- External scientific evidence to `sancai-researcher`.
- Scientific/numerical validity to `sancai-science-auditor`.

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

## Human boundary

The human designs the loop and signs the intent/outcome. PM may propose; only
the human signs, approves irreversible actions, and accepts the outcome.
