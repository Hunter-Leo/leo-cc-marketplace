# leo-cc-marketplace

A curated collection of Claude Code plugins for productivity, development workflows, and team collaboration.

## Plugins

| Plugin | Description |
|--------|-------------|
| [example-plugin](plugins/example-plugin) | Starter plugin demonstrating Claude Code plugin structure |

## Usage

### Add this marketplace

```bash
# From GitHub (once pushed)
/plugin marketplace add Fightinglee/leo-cc-marketplace

# Or from local path
/plugin marketplace add ./path/to/leo-cc-marketplace
```

### Install a plugin

```bash
/plugin install example-plugin@leo-cc-marketplace
```

### Verify installation

```bash
/plugin list
```

## Development

### Prerequisites

- [Claude Code](https://claude.ai/code) installed

### Local testing

```bash
# Validate marketplace structure
claude plugin validate .

# Add marketplace locally
/plugin marketplace add .

# Install a plugin
/plugin install example-plugin@leo-cc-marketplace
```

### Creating a new plugin

```bash
# Create plugin directory
mkdir -p plugins/my-plugin/.claude-plugin
mkdir -p plugins/my-plugin/skills/my-skill

# Create plugin manifest (plugin.json)
# Create skill file (SKILL.md)
# Add entry to .claude-plugin/marketplace.json
```

## License

MIT
