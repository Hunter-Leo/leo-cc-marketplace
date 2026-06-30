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

See the [docs](docs/) directory for detailed usage guides, workflows, and best practices for each component.

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
