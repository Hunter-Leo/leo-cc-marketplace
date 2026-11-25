# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Repo Is

A Claude Code plugin marketplace (`leo-cc-marketplace`) hosted at `Hunter-Leo/leo-cc-marketplace`. Users add it via `/plugin marketplace add Hunter-Leo/leo-cc-marketplace` to install plugins.

## Structure

```
.claude-plugin/marketplace.json    ← Marketplace catalog (plugin index)
plugins/
  ├── leo-dev-plugin/               ← Single-agent toolkit
  │   ├── .claude-plugin/plugin.json
  │   ├── commands/                  ← Slash commands (agnes-json-img, calm, dev-init)
  │   └── skills/
  │       └── spec-coding-skill/     ← Skill with SKILL.md + references/
  ├── leo-team-plugin/              ← Classic multi-agent team toolkit
  │   ├── .claude-plugin/plugin.json
  │   ├── agents/                    ← 6 team roles (spec-*)
  │   ├── commands/                  ← spec-team, team-status, team-reset
  │   ├── hooks/hooks.json           ← Flow enforcement
  │   ├── scripts/                   ← flow.sh, validate-lane-write.sh, check-team-complete.sh
  │   └── skills/
  │       ├── agent-team-authoring/  ← How to design an agent team
  │       └── spec-coding-team-skill/← Team workflow (phases, references, templates)
  └── sancai-loop-plugin/                   ← Agent-in-the-loop harness (MVP)
      ├── .claude-plugin/plugin.json
      ├── agents/                    ← sancai-executor, sancai-verifier
      ├── commands/                  ← sancai (start / approve / accept / status / abandon)
      ├── hooks/hooks.json           ← Sancai guards (no-op unless .sancai/active)
      ├── references/                ← coding standards, git workflow, progress updates, capability table
      ├── scripts/                   ← sancai_paths.py, sancai_state.py, sancai_check_ac.py, sancai_capability.py, sancai_gate.py, sancai_hook.py, sancai_decide.py
      └── skills/
          └── sancai-loop/          ← Three-layer loop (L3 Intent → L2 Harness → L1 Code)
```

`plugins/` root holds all plugin directories. Each plugin has its own `.claude-plugin/plugin.json`.

## Commands

- **Validate marketplace**: `claude plugin validate .`
- **Validate a plugin**: `claude plugin validate ./plugins/<name>`
- **Add marketplace locally**: `/plugin marketplace add .`
- **Install plugin**: `/plugin install leo-dev-plugin@leo-cc-marketplace`

## Adding a New Plugin

1. Create `plugins/<name>/.claude-plugin/plugin.json` with name, description, version
2. Add skills under `plugins/<name>/skills/<skill-name>/SKILL.md`
3. Add commands under `plugins/<name>/commands/<name>.md`
4. Add entry in `.claude-plugin/marketplace.json` `plugins` array

## Plugin Inventory

| Plugin | Contents |
|--------|----------|
| `leo-dev-plugin` | `agnes-json-img` (Agnes AI JSON prompt command), `calm` (debug pause command), `spec-coding-skill` (spec-driven round-based coding workflow with references and utility scripts) |
| `leo-team-plugin` | `agent-team-authoring` (how to design an agent team), `spec-coding-team-skill` (PM-led multi-agent workflow), `spec-team` / `team-status` commands, 6 `spec-*` team roles, flow-enforcement hooks |
| `sancai-loop-plugin` | `sancai-loop` (Agent-in-the-loop three-layer loop), `/sancai` entrypoint with `start` / `approve` / `accept` / `status` / `abandon`, `sancai-executor` / `sancai-verifier` agents, harness-owned evidence and capability tokens |

## Spec-Driven Development

For spec-driven development workflow, see [plugins/leo-dev-plugin/skills/spec-coding-skill/SKILL.md](plugins/leo-dev-plugin/skills/spec-coding-skill/SKILL.md) — covers Phase A (需求构建) through Phase B (需求执行) with hard gates, execution discipline, and utility scripts.

## Agent-in-the-Loop (AITL)

Implemented in **`plugins/sancai-loop-plugin`** (the classic `leo-team-plugin` is unchanged). Three layers:

- **L3 Human** signs `L3-intent/intent.json` (goal / AC / risk policy / budget).
- **L2 Harness** keeps `L2-harness/run.json`, creates Work Orders, runs G0/G3 gates, collects evidence, handles escalations.
- **L1 Code** runs an isolated `sancai-executor`; `sancai-verifier` judges independently.

Runtime state is physical: `.sancai/runs/<run>/{L3-intent,L2-harness,L1-code,audit}/`.

Commands: `/sancai start`, `/sancai approve`, `/sancai accept`, `/sancai status`, `/sancai abandon`.
`run` and `check` are internal: after H1 the PM agent runs add-wo → claim → executor → G0 → G3 → gate automatically.

Design: [docs/sancai/design/loop-design.md](docs/sancai/design/loop-design.md) · Eval plan: [docs/sancai/eval/phase-minus-1-eval.md](docs/sancai/eval/phase-minus-1-eval.md) · Eval harness: [evals/](evals/).

MVP is single-repository, single-writer, serial — **no worktree**. Key invariants: harness-owned evidence, independent verifier, fail-closed tool capability table, one-time capability tokens for irreversible actions. The plugin is **not a sandbox**; pair it with OS-level isolation.
