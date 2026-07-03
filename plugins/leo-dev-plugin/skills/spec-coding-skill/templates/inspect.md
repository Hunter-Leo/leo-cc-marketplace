# Inspect — [NNN]-[req-name]

## When to Use

Choose inspect when you need to understand existing code before making changes: static analysis, runtime tracing, dependency mapping. For technology evaluation, use `research.md` instead.

## Inspection Method

- **Static analysis** — read code structure, call graphs, data flow
- **Runtime trace** — observe execution path with real or test input
- **Dependency graph** — map module/file relationships
- **Logging analysis** — examine existing log output for patterns

## Scope

What code or system was inspected, and why. Define the boundaries of what was examined.

## Findings

| # | Location | Severity | Evidence | Recommendation |
|---|----------|----------|----------|----------------|
| 1 | file:line | high/med/low | observation or data | suggested action |

## Recommendations

What actions to take based on the findings. Rank by priority.
