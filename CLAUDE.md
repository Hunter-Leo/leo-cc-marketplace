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
  └── leo-team-plugin/              ← Multi-agent team toolkit
      ├── .claude-plugin/plugin.json
      ├── agents/                    ← 6 team roles (spec-*)
      ├── commands/                  ← spec-team, team-status
      ├── hooks/hooks.json           ← Flow enforcement
      ├── scripts/                   ← flow.sh, validate-lane-write.sh, check-team-complete.sh
      └── skills/
          ├── agent-team-authoring/  ← How to design an agent team
          └── spec-coding-team-skill/← Team workflow (phases, references, templates)
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

## Spec-Driven Development

For spec-driven development workflow, see [plugins/leo-dev-plugin/skills/spec-coding-skill/SKILL.md](plugins/leo-dev-plugin/skills/spec-coding-skill/SKILL.md) — covers Phase A (需求构建) through Phase B (需求执行) with hard gates, execution discipline, and utility scripts.
