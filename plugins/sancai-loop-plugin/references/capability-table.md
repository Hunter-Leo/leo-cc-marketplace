# Capability Table (tool capability model)

> The first gate for irreversible actions. Unlisted tools are denied by default (fail closed).

## Shape

```json
{
  "Read":  {"reversible": true,  "network": false, "mutates_external_state": false},
  "Write": {"reversible": true,  "network": false, "mutates_external_state": false},
  "Edit":  {"reversible": true,  "network": false, "mutates_external_state": false},
  "Bash":  {
    "reversible": false,
    "network": false,
    "mutates_external_state": true,
    "allowed_commands": ["npm test", "git diff", "rg "]
  },
  "mcp__email__send":      {"reversible": false, "network": true, "mutates_external_state": true},
  "mcp__github__merge_pr": {"reversible": false, "network": true, "mutates_external_state": true}
}
```

## Decision

```text
reversible = true if and only if:
  1. it only touches paths inside owned_files
  2. git revert can fully undo it
  3. it has no external side effect (email / payment / external API / permissions / production DB)
  4. data_impact == none

Otherwise it is irreversible.
```

## Rules

- A tool not in the table is denied.
- `Write` / `Edit`: the path must be inside the active claim's `owned_files`.
- `Bash`: the command must match an `allowed_commands` prefix.
- MCP tools use the same table; they are not parsed as Bash.
- Version the capability table; changes require human sign-off.

## Irreversible actions

Even when the capability table allows an action, an irreversible action still needs a **one-time human capability token**:

```bash
SANCAI_SECRET=<outside workspace> \
python3 scripts/sancai_capability.py mint --run <run> --action "<action>" --diff-sha "<sha>"
```

The token binds action + diff + nonce + expiry. It is single-use, and the agent cannot mint it.

## Boundary

The plugin is not a sandbox. Arbitrary syscalls inside a process, and behavior not wrapped by a tool, must be contained by an OS sandbox, devcontainer, or least-privilege account.
