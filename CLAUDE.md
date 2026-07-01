# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Repo Is

A Claude Code plugin marketplace (`leo-cc-marketplace`) hosted at `Hunter-Leo/leo-cc-marketplace`. Users add it via `/plugin marketplace add Hunter-Leo/leo-cc-marketplace` to install plugins.

## Structure

```
.claude-plugin/marketplace.json    ← Marketplace catalog (plugin index)
plugins/
  └── leo-dev-plugin/               ← The only plugin
      ├── .claude-plugin/plugin.json
      ├── commands/                  ← Slash commands (agnes-json-img, calm)
      └── skills/
          └── spec-coding-skill/     ← Skill with SKILL.md + references/
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

## Spec-Driven Development

For spec-driven development workflow, see [plugins/leo-dev-plugin/skills/spec-coding-skill/SKILL.md](plugins/leo-dev-plugin/skills/spec-coding-skill/SKILL.md) — covers Phase A (需求构建) through Phase B (需求执行) with hard gates, execution discipline, and utility scripts.
