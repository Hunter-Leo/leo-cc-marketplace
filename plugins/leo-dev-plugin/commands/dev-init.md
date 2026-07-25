---
description: Initialize local Claude Code environment — CLI tools, plugins, skills, MCP servers, and CLAUDE.md
argument-hint: [global|project]
allowed-tools: Read, Bash, Write, Edit
---

# /dev-init

Interactive environment initialization for Claude Code. Checks and recommends installation of CLI tools, plugins, skills, MCP servers, and CLAUDE.md baseline configuration.

## Flow

1. **Ask scope**: confirm whether to operate on global (`~/.claude/`) or project scope
2. **CLI tools**: check each recommended tool, report status, and offer install guidance
3. **Plugins**: check enabledPlugins in settings.json, recommend missing entries
4. **Skills**: check `~/.claude/skills/` or project `.claude/skills/`, recommend missing
5. **MCP**: verify recommended MCP servers are configured
6. **CLAUDE.md**: check non-OMC baseline content exists; offer to write it
7. **Summary**: report what's present, what's missing, and what was configured

## Scope detection

If `$ARGUMENTS` is "global" or "g", scope to `~/.claude/`. If "project" or "p", scope to `.claude/` in the current working directory. If empty, first determine the current working directory and ask the user.

```bash
# Determine scope from argument if provided
SCOPE="${1:-}"
```

## CLI tools to check

Use `which`/`command -v` to check each tool. Report status: ✓ installed, ✗ missing.

For missing tools, provide install guidance (reference `docs/dev-init-install-ref.md` in this plugin for authoritative install methods):

| Tool | Check command | Recommendation |
|------|-------------|----------------|
| uv | `command -v uv` | Required: Python package manager |
| nvm | `command -v nvm` and `export NVM_DIR="$HOME/.nvm"` then `[ -s "$NVM_DIR/nvm.sh" ]` | Required: Node.js version manager |
| bun | `command -v bun` | Recommended: JS runtime |
| gh | `command -v gh` | Recommended: GitHub CLI |

For each missing tool, ask the user if they want to install it. If yes, follow the install instructions from the reference file.

## Plugins to check

Read settings.json at the target scope. Check `enabledPlugins` for each recommended plugin:

| Plugin | Marketplace | Install command |
|--------|------------|----------------|
| oh-my-claudecode | omc | Add marketplace `Yeachan-Heo/oh-my-claudecode` then install |
| superpowers | claude-plugins-official | `/plugin install superpowers@claude-plugins-official` |
| skill-creator | claude-plugins-official | `/plugin install skill-creator@claude-plugins-official` |
| pyright-lsp | claude-plugins-official | `/plugin install pyright-lsp@claude-plugins-official` |

Check if the marketplace source is registered in `extraKnownMarketplaces` or `settings.json`. For each missing plugin, ask the user if they want to enable/install it.

## Skills to check

Check `~/.claude/skills/` (global) or `./.claude/skills/` (project) for each recommended skill:

| Skill | Install method |
|-------|---------------|
| deli-autoresearch | Already in `~/.claude/skills/` (check if present) |
| colab-session-operator | `npx skills add googlecolab/google-colab-cli --skill colab-session-operator -g -a claude-code` (global) |

For each missing skill, ask the user if they want to install it.

## MCP servers to check

Check for recommended MCP server configurations. Read `~/.claude/settings.json` for `mcpServers` or check for `.mcp.json` files.

| MCP Server | What to check |
|-----------|---------------|
| context7 | Check if `mcpServers.context7` exists in settings, or if `@anthropic/claude-code-addon-context7` is installed |
| anysearch | Check if anysearch MCP server is configured |

For each missing MCP server, ask the user if they want to add it. Provide install guidance from the reference file.

## CLAUDE.md baseline

Read the existing CLAUDE.md at the target scope. Check the non-OMC content status:

1. Locate the `<!-- OMC:START -->...<!-- OMC:END -->` block (skip, OMC manages this)
2. Audit the content outside the OMC block:
   - Is Coding Guidelines (or equivalent development conventions) present?
   - Is there any existing RTK.md or tool-specific configuration reference?
   - Does the overall structure separate concerns clearly?
3. If baseline content is missing or incomplete, ask the user whether to **integrate** the recommended baseline (Coding Guidelines + RTK.md reference) into their existing CLAUDE.md, preserving any content they already have.

The baseline content to offer is derived from the user's own global CLAUDE.md — read it at the global scope (`~/.claude/CLAUDE.md`) and extract the Coding Guidelines and RTK.md sections. Never hardcode a specific user path in the command file; always source content from the user's global configuration at runtime.

## Summary

At the end, produce a markdown summary table:

```
## dev-init Summary

| Category | Status | Details |
|----------|--------|---------|
| CLI Tools | 3/4 ✓ | uv ✓, nvm ✓, bun ✓, gh ✗ (skipped) |
| Plugins | 3/4 ✓ | oh-my-claudecode ✓, superpowers ✓, skill-creator ✓, pyright-lsp ✗ (skipped) |
| Skills | 1/2 ✓ | deli-autoresearch ✓, colab-session-operator ✗ (installed) |
| MCP | 1/2 ✓ | context7 ✓, anysearch ✗ (not configured) |
| CLAUDE.md | ✓ | Baseline present |
```

## Interaction pattern

Throughout the command, for each item that is missing, ask the user:

> **{Item}** is missing. Install/configure? [y/N]

Process their choice:
- `y`/`yes` → execute the install/configure action
- anything else → skip, add to summary as skipped

Group related questions when possible (e.g., "3 CLI tools missing. Install all? [y/N] [Choose individually]")
