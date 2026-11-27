# Run integration gate (G0-R)

Per-Work-Order G0 proves each slice. G0-R proves the slices still work together
before the run can reach H3. It is harness-run and evidence-bound; the PM cannot
declare integration passed from prose.

## Policy

`intent.integration_policy` is optional. Omitting it keeps the legacy
`executing → reviewing` path.

```json
{
  "required": true,
  "command": "npm test && npm run smoke",
  "timeout_seconds": 1800,
  "report": ".sancai/runs/<run>/L2-harness/integration/report.xml",
  "ignore_globs": [".sancai/**"]
}
```

- `command` is required when `required=true`; it runs from the repository root
  through the shell.
- `timeout_seconds` is an integer from 30 to 86400; default 1800.
- `report` is optional and must stay under
  `.sancai/runs/<run>/L2-harness/integration/`.
- `ignore_globs` extends the always-ignored `.sancai/**`.

## Flow

```text
last WO verified
   │
   ├─ no integration_policy ──► reviewing (legacy)
   └─ required ──► integrating
                     │
                     ▼
             sancai_integration.py check --run <run>
                     │
          ┌──────────┴───────────┐
          ▼                      ▼
       fail                   pass
          │                      │
          ▼                      ▼
transition --to executing   transition --to reviewing
add-wo --integration …      H3 acceptance
```

## Evidence

`L2-harness/integration/evidence.json` records:

`policy_sha`, `intent_revision`, `wo_state_sha`, `head`,
`pre_worktree_sha`, `post_worktree_sha`, `exit_code`, `timed_out`, `success`,
`output_head`, `output_sha`, `report`, `report_sha`, `started_at`,
`finished_at`, `evidence_sha`.

`success` requires exit 0, no timeout, and
`pre_worktree_sha == post_worktree_sha`. The worktree hash covers HEAD,
`git diff HEAD --binary`, and untracked file contents, excluding `.sancai/**`
and `ignore_globs`. An integration command that rewrites the tree fails the
gate.

Freshness is content-bound, not time-bound: entering `reviewing` checks the
policy hash, intent revision, Work Order state hash, HEAD, worktree, success,
evidence hash, and report hash. A stale attempt must be re-run with
`sancai_integration.py check` while the run is `integrating` or `reviewing`.

Failed attempts are archived under `integration/attempts/`. Repeated identical
attempts use the normal no-progress lease and can pause the run.

## Integration rework

1. `sancai_integration.py check --run <run>` fails and writes evidence.
2. `sancai_state.py transition --run <run> --to executing`.
3. `sancai_state.py add-wo --run <run> --integration --id WO-INT-001 --files …`
   (only allowed while `executing`, and only after a failed attempt).
4. Claim, execute, G0, G3 as usual.
5. When every WO is verified, the gate moves the run back to `integrating`.

A `WO-INT-*` has `req: null`, `kind: "integration"`, and does not count toward
selected-requirement coverage. It uses the same claim, executor, verifier, and
gate path as any other Work Order.

## Rules

- Only the harness writes integration evidence; agents submit through
  `sancai_integration.py`.
- `executing → reviewing` is refused when the policy requires integration.
- `integrating → reviewing` requires fresh passing evidence.
- `integrating → executing` and `reviewing → executing` require a failed
  attempt, so rework has a concrete reason.
- G0-R cannot replace H3. The human still accepts the run and its closeout.
