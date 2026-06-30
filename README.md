# leo-cc-marketplace

A curated collection of Claude Code plugins for productivity, development workflows, and team collaboration.

## Plugins

| Plugin | Description |
|--------|-------------|
| [leo-dev-plugin](plugins/leo-dev-plugin) | Personal dev toolkit — agnes-json-img command, calm debug command, and spec-driven coding skill |

## Usage

### Add this marketplace

```bash
/plugin marketplace add Hunter-Leo/leo-cc-marketplace
```

### Install a plugin

```bash
/plugin install leo-dev-plugin@leo-cc-marketplace
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
mkdir -p plugins/my-plugin/.claude-plugin
mkdir -p plugins/my-plugin/skills/my-skill
mkdir -p plugins/my-plugin/commands
```

## License

MIT
