# Plan — [NNN]-[req-name]
**Round:** [N]

## Project Structure

Show the intended directory and file layout. For modifications, show only affected parts and mark new/changed files.

```
src/
├── module_a/
│   ├── __init__.py
│   └── service.py
└── module_b/
    └── repository.py
```

## Technology Decisions

- Language version and runtime
- Key libraries and frameworks (with version constraints)
- Rationale for each significant choice
- Reference to `research.md` if Phase 02 was completed

## Implementation Path

Ordered list of implementation steps at the module level. Each step should be independently testable.

1. Implement `X` (depends on nothing)
2. Implement `Y` (depends on `X`)
3. Integrate `X` and `Y` in `Z`

## Key Technical Points

- Non-obvious design decisions and their reasoning
- Class and module design must follow OOP & SOLID principles — see `shared/01-oop-principles.md`
- Integration points between modules
- Error handling strategy
- Data flow between components
- Reference to `algorithm-design.md` if Phase 03 was completed

## Out of Scope

Explicitly list what this plan does **not** cover, to prevent scope creep.
