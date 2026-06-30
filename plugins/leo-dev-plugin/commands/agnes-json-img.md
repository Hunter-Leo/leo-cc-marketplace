---
description: Generate Agnes AI images driven by JSON-structured prompts — avoids shell escaping traps
argument-hint: <json-prompt-file.json>
---

# /agnes-json-img

Generate an Agnes image using a **JSON-structured prompt file**.
The JSON becomes the entire prompt string; no natural-language wrapper needed.

## Why this exists

Agnes `text2img --prompt` is a shell argument. When the prompt contains `#`, `$`, `"`, `{`, `(`, whitespace,
or backticks, the shell mangles the text before the CLI sees it — leading to truncated prompts or
`"Too small: expected string to have >=1 characters"` errors.

The fix: **pass the prompt through Python's `subprocess.run()`**, which bypasses shell interpolation entirely.

## Usage

```
/agnes-json-img /path/to/prompt.json
```

Then the agent will:

1. `jq -c '.' /path/to/prompt.json` → single-line compact JSON
2. Run the Python helper below to call `agnes image text2img` safely
3. Download the result
4. (Optional) feed it into the next step (PDF conversion, etc.)

## Python helper (inline; no install needed)

```python
import json, subprocess, sys

with open(sys.argv[1]) as f:
    prompt = json.dumps(json.load(f))   # compact, no newlines

result = subprocess.run(
    ['agnes', 'image', 'text2img',
     '--prompt', prompt,
     '--size', sys.argv[2] if len(sys.argv) > 2 else '1792x1024',
     '--json'],
    capture_output=True, text=True
)
print(result.stdout)
if result.stderr:
    print(result.stderr, file=sys.stderr)
```

## JSON prompt structure (recommended)

No `prompt` field — the whole JSON is the prompt. Describe *every visual element* as structured data.

```json
{
  "canvas": { "size": "1792x1024", "aspect_ratio": "16:9" },
  "background": {
    "type": "...",
    "base_color": "#0B1120",
    "overlay": { "pattern": "..." }
  },
  "subjects": [
    {
      "id": "main_subject",
      "type": "...",
      "position": { "center_x": ..., "center_y": ... },
      "colors": { "primary": "#...", "highlight": "#..." },
      "rendering": { "style": "...", "material": "...", "lighting": {...} },
      "sub_elements": [ ... ]
    }
  ],
  "atmosphere": {
    "particles": { "type": "...", "color": "#...", "opacity": 0.15 },
    "light_rays": { "source": "...", "opacity": 0.08 }
  },
  "style": {
    "aesthetic": "...",
    "influences": ["...", "..."],
    "color_grading": { "contrast": "medium_high" }
  },
  "constraints": {
    "no_text": true,
    "no_labels": true
  }
}
```

## One-liner (when the agent already has the JSON file)

```
python3 -c "
import json, subprocess
with open('prompt.json') as f: p=json.dumps(json.load(f))
r=subprocess.run(['agnes','image','text2img','--prompt',p,'--size','1792x1024','--json'],capture_output=True,text=True)
print(r.stdout)
" && curl -sL "$(python3 -c "import json,sys; print(json.loads(sys.stdin.read())['url'])" < /dev/stdin)" -o output.png
```

## Lessons learned

1. **Shell interpolation is the enemy of JSON prompts.** Don't fight it — route around it.
2. **`subprocess.run()` with a list** never invokes a shell. Each argument is passed verbatim.
3. **Compact JSON** (`jq -c`) eliminates embedded newlines that confuse line-oriented tools.
4. **`jq` for inspection, Python `json.dumps` for the final passthrough** — both guarantee valid UTF-8 without shell metacharacter exposure.
5. **Model interpretability**: Agnes Image 2.1 handles ~3,500-character structured JSON prompts well; the model maps structured descriptions to visual elements more faithfully than ad-hoc keyword lists.
