# Data Model Standard (Sancai)

> Read before defining an interface, a persisted artifact, or a schema change.
> Data model changes require an ADR and a migration plan.

## Core rules

| Rule | Requirement |
|---|---|
| Schema version | Every persisted JSON has `schema_version` |
| Identity | Stable `id`; link with `run_id`, `wo_id`, `evidence_sha` |
| Time | UTC ISO-8601; `created_at`, `updated_at` |
| Named models | No bare dict or positional tuple for a domain object |
| Enums | Fixed sets use `StrEnum` or `Literal` |
| Constraints | Bounded values use constrained types or explicit validators |
| Boundaries | Validate on read; core logic receives validated models only |
| Persistence | Atomic write via temp file + `os.replace`; mode 0600/0700 |
| Compatibility | New fields optional; old readers must still work |
| Migration | Breaking changes require migration + ADR + rollback |
| Secrets | Never persist tokens, keys, or secrets in artifacts or graph |
| Retention | Define retention; runtime artifacts are not committed |

## Python modeling

### When dependencies are allowed

Use Pydantic v2 for meaningful data structures:

- No bare `str`, `int`, or `float` as domain types.
- Use `StrEnum` or `Literal` for fixed sets.
- Use constrained types for bounds, e.g. `conint(ge=0)`.
- Field format: `Annotated[Type, Field(description=..., examples=[...])] = default`.

### Zero-dependency plugin scripts

Sancai scripts must remain runnable with the Python standard library. When
Pydantic is not available:

- Use `@dataclass(frozen=True)` or `TypedDict` for named shapes.
- Write an explicit `validate_*` function at the boundary.
- Never pass a raw `dict` into core logic after validation.
- Keep the same schema version and field names as the Pydantic model would use.

The contract is the schema, not the library.

## Prohibited shapes

| Pattern | Why | Alternative |
|---|---|---|
| `Dict[str, T]` with variable keys | Keys carry implicit meaning; no schema | `list[SomeModel]` with a named id field |
| `Tuple[str, str, int]` | Positional; no field names | Named dataclass or Pydantic model |
| `List[Dict[str, Any]]` | No type safety; no validation | Nested named models |
| Boolean flags that encode a state | Illegal states become representable | Enum or state machine |

Allowed: `Dict[Literal["x", "y"], float]` when the keys are fixed and known.

## Persisted artifact rules

Every artifact under `.sancai/runs/<run>/` must have:

```json
{
  "schema_version": 1,
  "id": "...",
  "run_id": "...",
  "created_at": "2026-01-01T00:00:00Z",
  "updated_at": "2026-01-01T00:00:00Z"
}
```

Additional rules:

- Write to a temp file in the same directory, then `os.replace`.
- Set directory mode `0700` and file mode `0600` for run state.
- Do not store secrets; redact environment values before writing evidence.
- `events.jsonl` is append-only; one JSON object per line.
- `graph.json` is derived; it may be rebuilt from `events.jsonl` and `run.json`.
- Do not commit `.sancai/`; commit distilled docs under `docs/`.

## Migration and compatibility

A schema change requires:

1. `design.md` section describing the change and its consumers.
2. `ADR` with context, decision, consequences, and alternatives.
3. A migration path for existing artifacts.
4. A rollback path.
5. A test that reads an old artifact and a new artifact.

Compatibility rules:

- Adding an optional field is backward compatible.
- Removing or renaming a field is breaking; bump `schema_version`.
- Changing a field's meaning is breaking even if the type is unchanged.
- Readers must reject unknown `schema_version` values explicitly; do not guess.

## AITL artifact examples

| Artifact | Key fields |
|---|---|
| `intent.json` | `id`, `goal`, `non_goals`, `acceptance[]`, `manual_ac_ratio`, `risk_policy_ref` |
| `run.json` | `run_id`, `state`, `intent_file`, `claim`, `work_orders[]` |
| `evidence/<WO>.json` | `wo`, `commands[]`, `diff_sha`, `collected_at`, `artifacts[]` |
| `verdicts/<WO>.json` | `wo`, `verdict`, `findings[]`, `evidence_sha`, `context_id` |
| `cards/<CARD>.json` | `card_id`, `kind`, `tier`, `payload`, `card_hash`, `card_code`, `used_at` |
| `events.jsonl` | `seq`, `ts`, `run_id`, `action`, `actor`, `subject`, `from`, `to`, `payload` |

## G3 checklist

- [ ] The change has a schema version and a migration plan.
- [ ] Domain objects are named models, not raw dicts or tuples.
- [ ] Fixed sets use enums or literals.
- [ ] Bounds and invariants are validated at the boundary.
- [ ] Writes are atomic and permissions are restrictive.
- [ ] No secret is persisted.
- [ ] Old artifacts remain readable, or the breaking change is explicit.
- [ ] The rollback path is documented.
