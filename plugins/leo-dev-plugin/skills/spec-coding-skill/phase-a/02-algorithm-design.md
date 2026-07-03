# Phase 03 — Algorithm Design

**Entry:** `init.md` exists, and the requirement involves non-trivial algorithms (search, optimization, data transformation, graph processing, etc.).
**Exit:** `algorithm-design.md` created with pseudocode and complexity analysis.

This phase is **optional**. Produce `algorithm-design.md` when the requirement involves implementing a non-trivial algorithm.

## Trigger Conditions

Activate this phase if the requirement involves any of the following:

- Graph algorithms (traversal, shortest path, cycle detection, etc.)
- Dynamic programming or memoization
- Custom data structures (trees, heaps, tries, etc.)
- Complexity-sensitive operations (the naive approach would be too slow)
- Concurrent or parallel processing logic
- Complex state machines or rule engines

If the requirement only involves straightforward CRUD, simple data transformation, or calling existing library APIs, skip this phase.

## algorithm-design.md Template

Read the template at `templates/algorithm-design.md`, then create `.dev/[NNN]-[req-name]/generated/algorithm-design.md`.

The template includes: Problem Analysis, Approach Options, Selected Approach, Data Structures, Diagrams, Use Cases & Examples, Pseudocode, and Complexity Summary.

## Rules

- Read `init.md § Constitution` to understand the coding constraints for this requirement before designing
- Read [../shared/01-oop-principles.md](../shared/01-oop-principles.md) before designing — ensure the algorithm and data structures are compatible with OOP & SOLID principles
- **Review the pseudocode for OCP violations** — if it contains `if/elif` chains that depend on type, replace with polymorphism before proceeding
- Complete this document and review it before writing any implementation code
- If the pseudocode reveals a flaw, revise the design here first
- Reference this document in `plan.md`

## After Completing Phase 03

If Phase 03 was executed, update `.dev/blueprint.md`: advance this requirement's Phase to `03 Algorithm` and Status to `✅ done` for this phase.
