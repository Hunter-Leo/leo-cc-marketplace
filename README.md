# leo-cc-marketplace

A curated collection of Claude Code plugins for productivity, development workflows, and team collaboration.

## Quick Start

```bash
# Add the marketplace
/plugin marketplace add Hunter-Leo/leo-cc-marketplace

# Install the plugin
/plugin install leo-dev-plugin@leo-cc-marketplace

# Verify
/plugin list
```

## Plugins

### leo-dev-plugin

Personal development toolkit with commands and skills:

| Component | Usage | Description |
|-----------|-------|-------------|
| `/agnes-json-img` | `/agnes-json-img prompt.json` | Generate Agnes AI images from structured JSON prompts — avoids shell escaping traps |
| `/calm` | `/calm` | Pause, reset, and analyze when stuck on a bug. Forces structured root-cause analysis before proposing fixes. Helps mitigate LLM context anxiety by breaking the cycle of rushed fixes |
| `/spec-coding-skill` | `/spec-coding-skill` | Spec-driven, round-based coding workflow: initialization → prereq tasks → algorithm design → implementation plan → task planning → execution. Includes TDD, debugging, architecture review, and dual-axis review methods |

See the [plugin docs](plugins/leo-dev-plugin/docs/) for detailed usage guides, workflows, and best practices for each component.

### leo-team-plugin

Experimental multi-agent workflow for M-sized and larger requirements. A PM-led Agent Team runs a spec-driven pipeline — Phase A → hard user gate → formation → parallel execution → round review → verification — with mechanical state control and an optional science-fact review lane.

| Component | Usage | Description |
|-----------|-------|-------------|
| `/spec-team` | `/spec-team <requirement or .dev path>` | Start the team workflow. Detects Agent Teams availability and never silently degrades to subagents |
| `/team-status` | `/team-status [run]` | Read-only progress report: Goal / Progress / Active / Blockers / Next |
| `/team-reset` | `/team-reset <run>` | Archive a finished run's runtime state without deleting it. Requires typing `archive` to confirm; refuses runs that are executing or hold a claim |

Requires Agent Teams in an interactive Claude Code session (`CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`). See the [plugin docs](plugins/leo-team-plugin/docs/spec-coding-team-skill.md) for roles, artifacts, and limitations.

## Local Development

### Validate

```bash
claude plugin validate .
claude plugin validate ./plugins/leo-dev-plugin
```

### Adding a new plugin

```bash
mkdir -p plugins/my-plugin/.claude-plugin
mkdir -p plugins/my-plugin/skills/my-skill
mkdir -p plugins/my-plugin/commands
# Create plugin.json, SKILL.md, then add entry to .claude-plugin/marketplace.json
```

## License

MIT
