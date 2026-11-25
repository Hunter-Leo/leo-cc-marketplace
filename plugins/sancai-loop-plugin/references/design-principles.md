# Design Principles (Sancai)

> Read before writing `design.md`, before implementing an M/L Work Order, and
> before G3 verification. These principles guide design; they do not replace
> the acceptance criteria or the verifier.

## AITL principles

Sancai adds five execution principles to OOP and SOLID:

1. **Change locality** — one Work Order changes only its `owned_files`; a
   cross-file refactor is a separate Work Order.
2. **Explicit boundaries** — modules communicate through named interfaces and
   validated data models, never through hidden global state.
3. **Testability** — core logic is pure where possible; side effects live at
   the boundary; tests are deterministic.
4. **Observability** — critical paths emit structured events or logs; secrets
   never enter logs, evidence, or the process graph.
5. **Reversibility** — keep diffs small; irreversible actions require H2;
   data changes require a migration and a rollback path.

## OOP

| Principle | Rule | Review question |
|---|---|---|
| Encapsulation | Keep internal state private; expose only what callers need | Can a caller mutate internals without going through the interface? |
| Abstraction | Callers depend on contracts, not implementation details | Would changing the implementation break callers? |
| Inheritance | Use only for genuine `is-a`; prefer composition when in doubt | Is this relationship truly `is-a`, or just shared code? |
| Polymorphism | New variants extend the design without editing callers | Does a new case require editing a long `if/elif` chain? |

## SOLID

| Principle | Rule | Sancai check |
|---|---|---|
| S — Single Responsibility | One class or function has one reason to change | If the description needs "and", split it |
| O — Open/Closed | Add behavior by adding code, not by editing tested code | New case should be a new implementation, not another branch |
| L — Liskov Substitution | A subtype must be usable wherever the parent is expected | Does the subtype weaken preconditions or strengthen postconditions? |
| I — Interface Segregation | Prefer small, focused interfaces | Are implementors forced to provide unused methods? |
| D — Dependency Inversion | High-level modules depend on abstractions | Is a dependency constructed inside the class instead of injected? |

OCP is the highest-leverage principle for agent-generated code: it limits the
blast radius of a new requirement. Use abstract base classes, protocols, or
strategy objects as extension points.

## Design patterns

Use a pattern only when it creates a real extension point.

| Pattern | Use when |
|---|---|
| Factory / Factory Method | Creation logic is complex or varies by type |
| Strategy | Algorithms or policies must be swapped at runtime |
| Observer | One change must notify multiple dependents |
| Repository | Data access must be decoupled from business logic |
| Decorator | Behavior must be added without subclassing |
| Singleton | Exactly one instance is required; use sparingly |

## Proportionality

| Size | Design requirement |
|---|---|
| XS | No `design.md`; OOP/SOLID still applies to stateful code |
| S | Short `design.md`; note any intentional deviation |
| M | Full `design.md`; ADR for interface, data, or irreversible decisions |
| L | Full `design.md` + ADR + staged Work Orders + H1 plan approval |

A pure function or a one-shot script may use a functional style. A stateful
domain object, adapter, or policy must justify why it is not a class. "It is
shorter" is not a justification for hidden global state.

## G3 review checklist

- [ ] The design keeps changes inside `owned_files`.
- [ ] Public behavior is expressed through named interfaces.
- [ ] State is encapsulated; no mutable module-level globals were introduced.
- [ ] New variants use extension points instead of editing tested branches.
- [ ] Dependencies are injected, not constructed inside domain logic.
- [ ] Data crossing a boundary is validated.
- [ ] Errors are explicit; no silent fallback.
- [ ] The design has a rollback path.
- [ ] Any OOP/SOLID deviation is documented in `design.md`.

## Anti-patterns

- A "God object" that owns parsing, persistence, and policy.
- A long `if/elif` chain that must be edited for every new case.
- A class that is only a namespace for unrelated functions.
- A global mutable singleton used as a dependency injection shortcut.
- An abstraction introduced before the second use case exists.
- A subclass that changes the parent's contract.
- A data model made of variable-key dictionaries or positional tuples.
