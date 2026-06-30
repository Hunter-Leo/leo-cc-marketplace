# leo-cc-marketplace

A curated collection of Claude Code plugins for productivity, development workflows, and team collaboration.

## Usage

### Add this marketplace

```bash
/plugin marketplace add Hunter-Leo/leo-cc-marketplace
```

### Install a plugin

```bash
/plugin install <plugin-name>@leo-cc-marketplace
```

### Verify

```bash
/plugin list
```

## Development

### Validate marketplace structure

```bash
claude plugin validate .
```

### Creating a new plugin

```bash
# Create plugin structure
mkdir -p plugins/my-plugin/.claude-plugin
mkdir -p plugins/my-plugin/skills/my-skill

# Create plugin manifest
# then add entry to .claude-plugin/marketplace.json
```

## License

MIT
