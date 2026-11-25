# Execution Discipline (Sancai L1)

> These rules apply to every executor during L1. They are process requirements,
> not suggestions. Violations are G0/G3 findings.

## Before writing

1. Read `run.json` and confirm the active claim's `wo` is your Work Order.
2. Confirm every path you will write is in `owned_files`.
3. Read the intent excerpt and the acceptance criteria for your Work Order.
4. Read the relevant standards:
   - `design-principles.md`
   - `coding-standards.md`
   - `comment-standard.md`
   - `data-model-standard.md`
   - `verification-standard.md`
   - `execution-discipline.md`
5. Read the files you will change before editing them.

If the claim does not match, stop and report `BLOCKED`. Do not claim or release
on your own.

## Read before write

- Read the target file and its immediate dependencies before editing.
- Do not edit by pattern matching alone; understand the surrounding contract.
- If the file is longer than you can read, read the relevant sections and state
  which sections you read.

## Scope discipline

- Keep changes inside `owned_files`.
- Aim for 3–5 files per Work Order. More files require a reason in the progress log.
- Write one file at a time; do not batch unrelated edits.
- A file over 200 lines that you are creating or substantially rewriting needs a
  short justification in the progress log.
- Do not perform a cross-Work-Order refactor. Create a separate Work Order.
- Do not fix unrelated bugs in the same Work Order; log them in `issues.md`.

## Tests and evidence

- Write tests in the same Work Order as the code they cover.
- Run the acceptance commands locally before reporting.
- Do not weaken tests, skip tests, or replace behavior with stubs.
- Do not write `evidence/` or `verdicts/`; the harness owns them.
- Do not declare "done"; the gate decides.

## Progress

Record progress after each meaningful step:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/sancai_state.py" progress \
  --wo <WO-ID> --status doing --item "implement rotation"
```

Progress entries are for the human and the audit graph, not for claiming
completion.

## Escalation

Escalate instead of guessing:

1. **Irreversible** — delete, force-push, pay, deploy, change permission.
2. **Out of scope** — a file outside `owned_files`, a new dependency, or
   production access.
3. **Spec ambiguous** — acceptance criteria conflict or are missing.

Use the structured escalation command; include what you tried, evidence, options,
recommendation, and confidence.

## Prohibited

- Writing outside `owned_files`.
- Writing evidence or verdicts.
- Declaring done.
- `git push`, merge to main, or any irreversible action.
- Weakening tests to make them pass.
- Hardcoding secrets.
- Silently expanding scope.
- Editing a file you did not read.
- Batching unrelated edits into one Work Order.
