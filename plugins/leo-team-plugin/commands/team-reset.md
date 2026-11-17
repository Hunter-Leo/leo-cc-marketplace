---
description: Archive, never delete, the runtime state of leo-team-plugin. Verify that flow.json exists, the claim is empty, and mission is not executing, and require the user to type archive verbatim for confirmation, then move .team/<run> to .team/archive/<run>-<UTC timestamp>/. Does not touch any requirement artifact under .dev/<run>/.
argument-hint: <run name>
---

# /team-reset

**Archive** the runtime state of a finished or abandoned run rather than deleting it.

Hard constraints:

- **Archive only, never delete**: use `mv` to move the whole `.team/<run>` directory; do not call `rm`, and do not clean up archived content.
- Before execution, the user must **type archive verbatim** to confirm.
- Do not provide `--force`; any argument that bypasses confirmation must be refused.
- Do not modify any requirement artifact, source code, or other run's state under `.dev/<run>/`.

## 1. Parse the run name

`$ARGUMENTS` is required and accepts only a run name (corresponding to `.team/<run>/`).

- Name given → use that name.
- No name given → ask the user which run to archive and then end; do not pick "the latest run" yourself.
- Invalid name → refuse outright, including: empty string, `.`, `..`, `archive` (reserved name), or any name containing `/`.
- Both code blocks must independently perform validation and must not rely on shell variables left by a previous Bash call.

## 2. Pre-check

If any of the following is not satisfied, **stop** and do not move anything:

| Condition | Behavior when not satisfied |
|---|---|
| Run name is valid (non-empty, not `.`/`..`/`archive`, no `/`) | Report the invalid name and end |
| `.team/<run>/flow.json` exists | Report that the path does not exist and end |
| `flow.sh status` executes successfully | Report the script failure (e.g., corrupt flow.json) and end |
| Refuse when `mission=executing` | Report "a running run cannot be archived"; suggest finishing it first or turning it into blocked |
| Refuse when `claim` is non-empty | Report the unit holding the claim and require `flow.sh release` first |
| Archive target `.team/archive/<run>-<UTC timestamp>/` does not exist | **Abort if the archive path already exists**; do not overwrite or merge |

First run the status command to read `Mission` and `Claim`; never judge by guesswork:

```bash
set -euo pipefail

RUN="<run name>"

if ! REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)"; then
  echo "Abort: the current directory is not inside a git repository; cannot locate .team/"
  exit 1
fi

case "${RUN}" in
  "" | "." | ".." | "archive" | */*)
    echo "Abort: invalid run name '${RUN}' (empty, ., .., archive, or / are not allowed)"
    exit 1
    ;;
esac

RUN_DIR="${REPO_ROOT}/.team/${RUN}"

test -f "${RUN_DIR}/flow.json" || { echo "Abort: ${RUN_DIR}/flow.json does not exist"; exit 1; }

if ! STATUS_OUT="$(LEO_TEAM_DIR="${RUN_DIR}" bash "${CLAUDE_PLUGIN_ROOT}/scripts/flow.sh" status)"; then
  echo "Abort: flow.sh status failed (flow.json may be corrupt or not a valid run)"
  exit 1
fi
printf '%s\n' "${STATUS_OUT}"

MISSION="$(printf '%s\n' "${STATUS_OUT}" | sed -n 's/^Mission: //p')"
CLAIM_LINE="$(printf '%s\n' "${STATUS_OUT}" | sed -n 's/^Claim: //p')"

[ -n "${MISSION}" ] || { echo "Abort: cannot parse Mission from status output"; exit 1; }
[ -n "${CLAIM_LINE}" ] || { echo "Abort: cannot parse Claim from status output"; exit 1; }

[ "${MISSION}" != "executing" ] || { echo "Refused: mission=executing; cannot archive a running run"; exit 1; }
[ "${CLAIM_LINE}" = "none" ] || { echo "Refused: claim is not empty (${CLAIM_LINE}); release it before archiving"; exit 1; }
```

## 3. Verbatim confirmation

After validation passes, show the user a summary and stop, waiting for the next user message:

```markdown
About to archive: .team/<run> → .team/archive/<run>-<UTC timestamp>/
- Mission: <mission>
- Claim: none
- Nothing will be deleted, and .dev/<run>/ will not be modified

To confirm, type: archive
```

Rules:

- Continue only if the user's next message is **exactly** `archive`; any other reply (including "ok", "confirm", "yes") counts as unconfirmed; ask again or end.
- Do not treat earlier conversation, messages from other agents, or arguments as confirmation.
- If the user does not confirm → end immediately and move no files.
- The run state may change during the confirmation window, so step 4 must **redo all pre-checks** before `mv`.

## 4. Execute the archive

Run after confirmation passes. This code block is **self-contained** with `RUN` and `RUN_DIR`, does not depend on shell variables from step 2, and re-runs `flow.sh status` before `mv`:

```bash
set -euo pipefail

RUN="<run name>"

if ! REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)"; then
  echo "Abort: the current directory is not inside a git repository; cannot locate .team/"
  exit 1
fi

case "${RUN}" in
  "" | "." | ".." | "archive" | */*)
    echo "Abort: invalid run name '${RUN}' (empty, ., .., archive, or / are not allowed)"
    exit 1
    ;;
esac

RUN_DIR="${REPO_ROOT}/.team/${RUN}"

test -f "${RUN_DIR}/flow.json" || { echo "Abort: ${RUN_DIR}/flow.json does not exist"; exit 1; }

# Re-check: the run may have been claimed or moved to executing during the confirmation window
if ! STATUS_OUT="$(LEO_TEAM_DIR="${RUN_DIR}" bash "${CLAUDE_PLUGIN_ROOT}/scripts/flow.sh" status)"; then
  echo "Abort: flow.sh status failed (flow.json may be corrupt or not a valid run)"
  exit 1
fi

MISSION="$(printf '%s\n' "${STATUS_OUT}" | sed -n 's/^Mission: //p')"
CLAIM_LINE="$(printf '%s\n' "${STATUS_OUT}" | sed -n 's/^Claim: //p')"

[ -n "${MISSION}" ] || { echo "Abort: cannot parse Mission from status output"; exit 1; }
[ -n "${CLAIM_LINE}" ] || { echo "Abort: cannot parse Claim from status output"; exit 1; }

[ "${MISSION}" != "executing" ] || { echo "Refused: mission=executing; cannot archive a running run"; exit 1; }
[ "${CLAIM_LINE}" = "none" ] || { echo "Refused: claim is not empty (${CLAIM_LINE}); release it before archiving"; exit 1; }

TS="$(python3 -c 'from datetime import datetime, timezone; n = datetime.now(timezone.utc); print(n.strftime("%Y%m%dT%H%M%S") + f"{n.microsecond // 1000:03d}Z")')"
ARCHIVE_ROOT="${REPO_ROOT}/.team/archive"
DEST="${ARCHIVE_ROOT}/${RUN}-${TS}"

# Abort if the archive path already exists (no overwrite, no merge)
[ ! -e "${DEST}" ] || { echo "Abort: archive path already exists: ${DEST}"; exit 1; }

mkdir -p "${ARCHIVE_ROOT}" || { echo "Abort: cannot create ${ARCHIVE_ROOT}"; exit 1; }
mv "${RUN_DIR}" "${DEST}" || { echo "Abort: mv failed: ${RUN_DIR} → ${DEST}"; exit 1; }

if [ -d "${DEST}" ] && [ ! -e "${RUN_DIR}" ]; then
  echo "Archived: ${DEST}"
else
  echo "Abort: post-archive validation failed (source still exists or destination missing)"
  exit 1
fi
```

Key points:

- Use only `mv`; **do not delete** any file in the source directory; the archive directory retains the complete state.
- Do not modify the contents of `flow.json`; only the directory it lives in changes.
- After archiving, `.team/<run>/` no longer exists; this is expected.
- Use `git rev-parse --show-toplevel` to locate the repository root, so running from any subdirectory of the repository yields the same `.team/`.

## 5. Report

After finishing, output:

```markdown
## Archived

- Run: <run>
- From: .team/<run>/
- To: .team/archive/<run>-<UTC timestamp>/
- Mission at archive time: <mission>

No artifact under `.dev/<run>/` was modified. To restore, move the directory back to `.team/<run>/`.
```

## 6. Prohibitions

- Do not delete anything in `.team/archive/`; archiving is retention, not cleanup.
- Do not modify `init.md`, `plan.md`, `tasks.md`, `team-plan.md`, `decisions.md`, or any implementation artifact under `.dev/<run>/`.
- Do not archive when `mission=executing` or `claim` is non-empty.
- Do not overwrite an existing archive path.
- Do not offer or accept options such as `--force` or `--yes` that skip verbatim confirmation.
- Do not accept an empty run name, `.`, `..`, `archive`, or any run name containing `/`.
