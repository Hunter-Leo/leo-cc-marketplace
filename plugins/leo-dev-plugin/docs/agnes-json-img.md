# agnes-json-img

Generate Agnes AI images using **JSON-structured prompt files**, bypassing shell interpolation issues.

## Why This Exists

Agnes CLI `text2img --prompt` takes a shell argument. When prompts contain `#`, `$`, `"`, `{`, whitespace, or backticks, the shell mangles the text before the CLI sees it — causing truncated prompts or `"Too small: expected string to have >=1 characters"` errors.

The fix: **pass the prompt through Python `subprocess.run()`**, which bypasses shell interpolation entirely.

## Workflow

```
1. Prepare a JSON prompt file  →  prompt.json
2. /agnes-json-img prompt.json
3. Agent reads → Python subprocess call → image downloaded
```

## Best Practices

### 1. Use `jq -c` for compact output

Before passing to the script, verify your JSON is valid and compact:

```bash
jq -c '.' prompt.json   # single-line, no embedded newlines
```

### 2. Describe every visual element

The entire JSON file is the prompt — no `prompt` wrapper field needed. Be structured:

```json
{
  "canvas": { "size": "1792x1024", "aspect_ratio": "16:9" },
  "background": {
    "type": "gradient",
    "base_color": "#0B1120",
    "overlay": { "pattern": "grid" }
  },
  "subjects": [
    {
      "type": "abstract_shape",
      "position": { "center_x": 0.5, "center_y": 0.5 },
      "colors": { "primary": "#00D4AA", "highlight": "#FF6B6B" }
    }
  ],
  "style": {
    "aesthetic": "cyberpunk",
    "color_grading": { "contrast": "high" }
  },
  "constraints": { "no_text": true, "no_labels": true }
}
```

### 3. Keep prompts under ~3,500 characters

Agnes Image 2.1 handles structured JSON up to this length well. Beyond that, fidelity degrades.

### 4. Use Python `json.dumps` for the final pass

```python
import json, subprocess
with open('prompt.json') as f:
    prompt = json.dumps(json.load(f))
result = subprocess.run(
    ['agnes', 'image', 'text2img', '--prompt', prompt, '--size', '1792x1024', '--json'],
    capture_output=True, text=True
)
```

This guarantees valid UTF-8 without shell metacharacter exposure. Shell interpolation is the enemy of JSON prompts — don't fight it, route around it.

## The One-Liner

When the agent already has the JSON file:

```bash
python3 -c "
import json, subprocess
with open('prompt.json') as f: p=json.dumps(json.load(f))
r=subprocess.run(['agnes','image','text2img','--prompt',p,'--size','1792x1024','--json'],capture_output=True,text=True)
print(r.stdout)
" && curl -sL "$(python3 -c "import json,sys; print(json.loads(sys.stdin.read())['url'])" < /dev/stdin)" -o output.png
```
