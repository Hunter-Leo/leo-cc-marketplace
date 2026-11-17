---
description: "Show leo-team-plugin team run progress. Locate .team/*/flow.json, run flow.sh status and check-team-complete.sh, and summarize findings.md / dead-ends.md, always emitting five sections: Goal / Progress / Active / Blockers / Next. Read-only; does not modify any file."
argument-hint: [run name or .dev requirement directory]---

# /team-status

This command is a **read-only** status report. Do not modify `flow.json`, source code, or any artifact; do not advance the phase.

## 1. Locate the run directory

Resolve in the following order:

1. `$ARGUMENTS` gives a run name → use `.team/<run>/flow.json`.
2. `$ARGUMENTS` gives a `.dev/<NNN>-<req>/` path → take the directory name `<NNN>-<req>` as the run name.
3. No arguments → list `.team/*/flow.json` and take the most recently modified one; if several exist, note in the output "N runs exist; showing the latest: <run>".

After locating, you may explicitly specify the run:

```bash
LEO_TEAM_DIR=".team/<run>" bash "${CLAUDE_PLUGIN_ROOT}/scripts/flow.sh" status
LEO_TEAM_DIR=".team/<run>" bash "${CLAUDE_PLUGIN_ROOT}/scripts/check-team-complete.sh"
```

When unspecified, you can also run directly (the script automatically picks the latest run):

```bash
bash "${CLAUDE_PLUGIN_ROOT}/scripts/flow.sh" status
bash "${CLAUDE_PLUGIN_ROOT}/scripts/check-team-complete.sh"
```

### When the run directory cannot be found

Do not report an error and do not create files. Output the startup guidance and end:

```markdown
## Goal
No team run record found (no `.team/*/flow.json`).

## Progress
None.

## Active
None.

## Blockers
None.

## Next
Run `/spec-team <requirement description>` to start a team flow; after the N0 decision passes, `.team/<req-name>/flow.json` will be created.
```

## 2. Collect status

1. Run `flow.sh status` and record: Run, Mission, Round, Branch, Science gate, Units, Claim, Blockers, Next.
2. Run `check-team-complete.sh` and record `OK` / `NOT COMPLETE` plus the blockers it lists / `NO RUN`.
3. Locate the artifact directory: prefer `.dev/<run>/generated/`; if it does not exist, take the most recently modified one under `.dev/*/generated/` and note the actual path in the output.
4. Read the `findings.md` summary:
   - Count `open` entries by severity (blocker / critical / major / minor / nit).
   - List only the first 5 entries among blocker, critical, and unaccepted major (ID + `file:line` + one sentence).
   - If the file does not exist, write "no findings.md".
5. Read the `dead-ends.md` summary:
   - Total entry count and the latest 3 entries (ID + attempt + one-sentence failure reason).
   - If the file does not exist, write "no dead-ends.md".

Summarize read-only; do not paste the full file contents or copy large blocks of logs.

## 3. Output format (fixed five sections)

```markdown
## Goal

<requirement ID and one-sentence goal; from init.md / team-plan.md; write "not recorded" if missing>

## Progress

- Mission: <planning | gate | executing | reviewing | verified | blocked>
- Round: <N>
- Branch: <name or not created>
- Units: pending=<n> in_progress=<n> for_review=<n> approved=<n> merged=<n> verified=<n> changes_requested=<n> blocked=<n>
- Completion: <OK | NOT COMPLETE (summary)>
- Artifact directory: <actual path>

## Active

- Claim: <unit / by / none>
- In progress: <in_progress / for_review / changes_requested units and owners>
- Write "none" when there are no active units

## Blockers

- flow.sh Blockers: <none or itemized>
- check-team-complete: <blockers from NOT COMPLETE>
- findings unresolved: <blocker/critical/unaccepted major summary>
- dead ends: <summary of the latest 3>
- Write "none" when all are empty

## Next

<quote the Next from flow.sh status directly; if there are unresolved blockers, add "PM must adjudicate/fix first, then continue">
```

## 4. Notes

- Status reflects only what is recorded on disk and does not mean teammates are still alive; before resuming execution you must re-spawn and obtain an acknowledgment from this session.
- `check-team-complete.sh` always exits 0; read the conclusion from the output text (`OK` / `NOT COMPLETE` / `NO RUN`).
- If `flow.json` cannot be parsed, report the error path and error message truthfully; do not guess the state.
