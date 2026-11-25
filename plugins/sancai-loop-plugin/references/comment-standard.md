# Comment Standard (Sancai)

> Docstrings are part of this standard. They are a G0/G3 gate, not a style
> suggestion. All comments and docstrings are English.

## Scope

```text
Comment standard
├── docstrings (module / class / function / public API / CLI)
├── inline comments (why / invariant / workaround)
├── TODO / FIXME / NOTE
└── prohibited patterns
```

## Required docstrings

| Object | Requirement |
|---|---|
| Every file | Module docstring: purpose, public API, side effects, dependencies |
| Every public class | Class docstring: responsibility, invariants, key attributes |
| Every public function/method | Summary, `Args`, `Returns`, `Raises`; add `Yields` when applicable |
| Private function | Required when the logic is non-obvious; optional for trivial accessors |
| CLI / script | Purpose, usage, arguments, environment variables, exit codes, side effects |
| Data model | Field meaning, units, constraints, defaults, invariants, schema version |
| Test | Behavior and scenario; optional when the test name is fully descriptive |
| Complex algorithm | ASCII diagram or concrete example; must be readable without external references |

A public API without a docstring fails G0. An empty docstring, `"""TODO"""`,
or `"""Returns the result."""` is treated as missing.

## Google-style templates

### Module

```python
"""Run-state and work-order transitions for Sancai Loop.

This module owns the L2 state machine. It does not execute code or call the
verifier; those are separate boundaries.

Side effects:
    Writes ``run.json``, ``events.jsonl``, and the active pointer.

Public API:
    cmd_init, cmd_transition, cmd_add_wo, cmd_accept
"""
```

### Class

```python
class CapabilityTable:
    """Maps tool actions to reversible/irreversible policy.

    Invariants:
        - Unknown actions are denied (fail closed).
        - A token is bound to action + diff_sha + nonce + expiry.

    Attributes:
        root: Repository root containing ``.sancai/capability-table.json``.
        policy: Parsed action policy keyed by tool family.
    """
```

### Function

```python
def consume_card(root: Path, card_id: str, code: str) -> dict:
    """Consume a one-time human decision card.

    Args:
        root: Repository root.
        card_id: Card identifier, e.g. ``CARD-7b55fe326ec7``.
        code: Eight-hex challenge rendered on the card.

    Returns:
        The consumed card payload.

    Raises:
        CardError: If the card is missing, tampered, expired, replayed, or the
            code does not match.

    Side effects:
        Marks ``used_at`` on disk; the card cannot be consumed again.
    """
```

### CLI / script

```python
"""Sancai human decision entrypoint.

Usage:
    python3 sancai_decide.py approve --run RUN --id ESC-001 \
        --card-id CARD-... --card-code ........

Exit codes:
    0  decision recorded
    2  invalid input or card verification failed
    3  human decision required but not confirmed

Side effects:
    Writes an approval or rejection record and an audit event.
"""
```

### Data model

```python
class WorkOrder(BaseModel):
    """A unit of executable work bound to one or more acceptance criteria.

    Attributes:
        id: Stable work-order identifier, e.g. ``WO-001``.
        owned_files: Repo-relative paths the executor may modify.
        acceptance: AC ids this Work Order claims to satisfy.
        state: One of pending/claimed/in_progress/for_review/verified/merged.
    """

    id: str
    owned_files: list[str]
    acceptance: list[str]
    state: WorkOrderState
```

## Content rules

1. The summary says what the object does, in one sentence; do not repeat the name.
2. Type annotations are the source of truth. `Args` describes semantics, units,
   ranges, constraints, and defaults; it does not repeat the type.
3. `Returns` describes meaning and shape, not "returns the result".
4. `Raises` lists every explicit exception and its trigger. Do not write only
   `Raises: Exception`.
5. Document side effects: file writes, network calls, global state, token use.
6. Document invariants and contracts: what must hold before and after the call.
7. Complex algorithms need an ASCII diagram or a concrete example.
8. Comments explain **why**, not **what**; code already shows what.
9. Update comments in the same Work Order as the code. Stale comments are defects.
10. All comments and docstrings are English.

## Inline comments

Allowed:

- A non-obvious reason for a design choice.
- A hidden constraint or invariant.
- A workaround, with the reason and removal condition.

```python
# Workaround: Claude Code hooks do not expose a stable session id in this
# version; fall back to the environment variable. Remove when fixed upstream.
```

Not allowed:

- Restating the code (`# increment i`).
- Commented-out code; use git history instead.
- A TODO without an owner and an issue.

## TODO / FIXME

```python
# TODO(owner, ISSUE-123): replace the text active pointer with JSON.
# FIXME(owner, ISSUE-456): remove the fallback after the upstream fix ships.
```

## Language variants

| Language | Format | Tool |
|---|---|---|
| Python | Google-style docstring | `ruff` D rules / `pydocstyle` |
| TypeScript / JavaScript | JSDoc with `@param`, `@returns`, `@throws` | ESLint `jsdoc` |
| Java | JavaDoc with `@param`, `@return`, `@throws` | Checkstyle / Javadoc |
| Bash | File header: purpose, usage, exit codes, env vars | shellcheck + review |

## Enforcement

```text
G0 (executor before submit)
├── formatter and linter pass
├── missing public docstring or type annotation -> fail
└── complex algorithm without example/diagram -> verifier returns it

G3 (verifier)
├── spot-check public docstrings for semantics, exceptions, side effects
├── check comments against the code
├── check TODO owner/issue
└── check for commented-out code

H3 (accept)
└── comment standard is part of the acceptance evidence
```

## Prohibited

- Empty or placeholder docstrings.
- Docstrings that contradict the code.
- Comments that merely restate the code.
- Commented-out code.
- TODOs without owner and issue.
- Non-English comments or docstrings.
