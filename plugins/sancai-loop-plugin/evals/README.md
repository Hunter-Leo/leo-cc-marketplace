# Sancai Loop plugin evals

Behavior-level regression tests for the `sancai-loop` plugin, run with
`claude plugin eval`.

These are **not** unit tests. Every run starts a real `claude -p` child process
and is billed to your account. The Python unit tests in `../tests/` stay the
cheap, deterministic layer.

Requirements:

- Claude Code `v2.1.269+` (this repo was tested on `2.1.276`)
- git `>= 2.31`
- A trusted local checkout; `--trust-plugin` skips the first-run prompt

## Cases

| Case | What it protects |
|---|---|
| `vague-goal-asks-candidates` | A vague goal triggers context-grounded intent candidates instead of code changes |
| `no-edit-before-intent` | No `Edit`/`Write` before the intent contract is confirmed |
| `no-completion-without-evidence` | Refuses to declare completion without G0/G3 evidence |
| `verifier-must-be-independent` | Refuses executor self-verification |
| `accept-requires-findings-ack` | Refuses H3 accept without `--ack-findings` / disposition |

The first case uses `fixture.sh` to scaffold a tiny Task API repository, so it
needs `--scaffold`. The scaffold runs as you, outside the eval sandbox; only run
cases from this trusted directory.

## Run one case while iterating

```bash
cd plugins/sancai-loop-plugin

claude plugin eval . \
  --case vague-goal-asks-candidates \
  --runs 1 \
  --scaffold \
  --ablation none \
  --trust-plugin
```

## Run the suite

```bash
cd plugins/sancai-loop-plugin
./evals/run.sh
```

`run.sh` pins `--model claude-sonnet-5` and `--judge-model claude-haiku-4-5`
because the eval child does not inherit every host model alias; override them
with `EVAL_MODEL` / `EVAL_JUDGE_MODEL`. It writes
`evals/results/aggregate.json` and fails below `EVAL_THRESHOLD` (default `0.8`).
Raise it to `1.0` only after every case is deterministic across several runs.

For CI, cap cost and disable report publishing:

```bash
EVAL_THRESHOLD=0.8 ./evals/run.sh \
  --max-cost-usd 20 \
  --no-publish \
  -j 4
```

## Design notes

- Prefer `regex` and `tool_used` graders; they are deterministic and cheap.
  Add an `llm` grader only where judgment is unavoidable.
- Each case needs at least one grader, otherwise it fails to load.
- `--ablation none` keeps local runs at one arm. Use the default
  `with-without` only when you want the plugin-vs-no-plugin delta.
- `results/` is gitignored; do not commit raw eval output.
- Passing this suite is not a security review. Plugin hooks and real MCP
  servers run outside the eval sandbox.
