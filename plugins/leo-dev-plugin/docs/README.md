# leo-dev-plugin Docs

Usage guides, workflows, and best practices for every component in leo-dev-plugin.

| Doc | Component | Type | Purpose |
|-----|-----------|------|---------|
| [agnes-json-img](agnes-json-img.md) | `/leo-dev-plugin:agnes-json-img` | Command | Generate Agnes AI images from structured JSON prompts |
| [calm](calm.md) | `/leo-dev-plugin:calm` | Command | Pause, reset, and analyze when stuck — mitigates LLM context anxiety |
| [spec-coding-skill](spec-coding-skill.md) | `/leo-dev-plugin:spec-coding-skill` | Skill | Spec-driven, round-based coding workflow for LLM agents |

## How to Use

All components are namespaced under the plugin. In Claude Code:

```
/<plugin-name>:<component>
/leo-dev-plugin:agnes-json-img prompt.json
/leo-dev-plugin:calm
/leo-dev-plugin:spec-coding-skill
```

Commands trigger immediately. The skill auto-activates by keyword trigger (`spec-driven`, `round-based`, `oop coding`, etc.) or can be called explicitly.
