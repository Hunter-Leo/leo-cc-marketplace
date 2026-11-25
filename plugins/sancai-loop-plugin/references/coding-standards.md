# Coding Standards (Sancai)

> Read before writing code. These rules apply to every language and every Work
> Order. Docstrings are in `comment-standard.md`; data shapes are in
> `data-model-standard.md`; tests are in `verification-standard.md`.

## Naming and language

- All identifiers, comments, docstrings, and commit messages are English.
- Follow the project language convention:
  - Python: `snake_case` for functions/variables, `PascalCase` for classes.
  - TypeScript/JavaScript: `camelCase` for functions/variables, `PascalCase` for
    types/classes.
  - Java: `camelCase` methods, `PascalCase` classes, `UPPER_SNAKE_CASE` constants.
- Names describe intent, not implementation. Avoid abbreviations that are not
  domain-standard.

## Types

- Every function parameter and return value has a type annotation. No untyped
  signatures in Python or JavaScript.
- Public interfaces in strongly typed languages declare explicit types.
- Do not use `Any`/`any` to bypass a type problem. Use `unknown` and narrow it,
  or define a proper model.
- Domain types are named models, not bare primitives. See
  `data-model-standard.md`.

## Code quality

- DRY: extract duplicated logic into a function or module.
- Single responsibility: one function does one thing; if the description needs
  "and", split it.
- Prefer early returns and guard clauses over deeply nested conditionals.
- Keep functions short. If each section needs a comment, split the function.
- Avoid speculative abstraction. Add an abstraction at the second real use case.
- No dead code, no commented-out code, no unused parameters.

## Structure and dependencies

- No circular dependencies between modules, directly or transitively.
- Fix a cycle by extracting shared types or utilities into their own module.
- `TYPE_CHECKING` is a last resort after restructuring, not the first fix.
- A flat module with a clean dependency direction is better than a deep tree
  with cycles.
- Import at the top of the file unless there is a concrete circular-import or
  startup-performance reason.
- Do not add a new dependency for a problem the standard library solves.

## Error handling

- Handle errors explicitly; never silently swallow an exception.
- Error messages are meaningful and actionable: what failed, why, and what to do.
- Distinguish recoverable errors (return or raise a domain error) from
  programming errors (let them propagate).
- Security, permission, and gate failures fail closed.
- Do not use exceptions for normal control flow.

## Security

- Never hardcode secrets, API keys, tokens, or passwords.
- Read secrets from environment variables or a secret manager; never log them.
- Validate and sanitize all external input.
- Avoid injection risks: parameterized SQL, escaped output, CSRF protection.
- Do not write secrets into evidence, verdicts, graph nodes, or progress files.
- Treat file paths from users or agents as untrusted: normalize and confine them.

## Performance

- Avoid N+1 query patterns.
- Use pagination or streaming for large data sets.
- Avoid unnecessary nested loops and repeated computation.
- Cache only with a documented invalidation strategy.
- Do not optimize before measuring; record the benchmark or profile when
  performance is an acceptance criterion.

## Tests

See `verification-standard.md` for the full test standard. Minimum:

- Normal, edge, and error cases for every behavior change.
- Core logic coverage at least 80%.
- Test through public interfaces, not private methods.
- Mock only at system boundaries.

## Documentation

See `comment-standard.md`. Every file, public class, and public function needs a
docstring. Comments explain why, not what.

## Dependencies and tools

- Python: `uv` for dependency and script management. Prefer `uv run`.
- TypeScript/JavaScript: `fnm` for Node versions, `pnpm` for packages.
- Java: Maven or Gradle, consistent within the project.
- Keep lockfiles updated and committed.
- Do not mix package managers within a project.

## Python

- Use type annotations on all parameters and return values.
- Prefer `pathlib.Path` over string path manipulation.
- Use `dataclass`/`TypedDict` for zero-dependency models; Pydantic v2 when the
  project already depends on it.
- Use `StrEnum` or `Literal` for fixed sets.
- Use `with` for files and resources.
- Avoid mutable default arguments.
- Use `subprocess.run(..., check=...)` with an explicit argument list, not
  `shell=True`.

## TypeScript / JavaScript

- Enable TypeScript `strict`.
- No `any`; use `unknown` and narrow it.
- Use interfaces or type aliases for all data shapes.
- Use enums or union types instead of string constants.
- Use Zod or an equivalent for runtime validation of external data.
- Use JSDoc on exported functions and classes.

## Java

- Use Bean Validation annotations on input models.
- Define interfaces or abstract classes as extension points.
- Use enums instead of string or int constants.
- Use JavaDoc on public classes and methods.
- Follow the OOP/SOLID rules in `design-principles.md`.

## Pre-commit self-check

- [ ] Formatter and linter pass.
- [ ] All tests pass; no regression.
- [ ] New behavior has normal/edge/error tests.
- [ ] Public APIs have type annotations and docstrings.
- [ ] No hardcoded secret or environment-specific value.
- [ ] No `.pyc`, log, `.DS_Store`, or `.sancai/` artifact staged.
- [ ] The diff stays inside `owned_files`.
- [ ] No test skipped, weakened, or stubbed.
