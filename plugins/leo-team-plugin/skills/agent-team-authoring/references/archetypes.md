# Role Archetypes: Classified by Verification Method

> A role's archetype is determined by **how its artifact is judged to hold**, not by what language it writes or which directory it touches.
> The same codebase can have two Builders, as long as their Lanes do not overlap; but one role cannot be both Builder and Adversary.

## Hard Rules

1. **A role can belong to only one archetype.** A mixed-archetype role cannot be scored: it is both player and referee, or both produces and verifies the output.
2. **Do not decompose by technical layer.** "Frontend / backend / test / ops / DBA" is the officially named problem-centric anti-pattern. It splits by the physical location of the problem, causing one verification method to be split into multiple roles while genuine independent verification is absent.
3. **The archetype determines the tool surface.** Decide the archetype first, then trim `tools:` accordingly. Doing it in reverse (give all tools first, then think about the role) yields a bunch of over-privileged general-purpose agents.

## Quick Reference

| # | archetype | How the artifact is verified |
|---|---|---|
| 1 | Coordinator | Is the plan executable, are adjudications recorded |
| 2 | Builder | Does the artifact actually run and pass |
| 3 | Adversary | Is the veto backed by evidence, was the veto actually exercised |
| 4 | Researcher | Can every conclusion be double-checked by a third party by opening the link |
| 5 | Explainer | Can the structure be used directly by downstream to make decisions |
| 6 | Contract Designer | Can downstream implement against it without follow-up questions |
| 7 | Verifier | Does every acceptance criterion have evidence |

---

## 1. Coordinator

**Criterion**: modifies no business artifacts itself; the artifacts are plans, task tables, adjudication records; has the power to say "no" to others and actually uses it.

**Typical artifacts**: `team-plan.md`, `tasks.md`, `decisions.md`, inquiry records for phase gates.

**Required tool surface**: plan file read/write + SendMessage + read-only code. **Do not give source write permission** — if given, it will definitely go and modify.

**Failure modes**:
- Overreach implementation: changes code "while at it", losing adjudication neutrality from then on.
- Work hoarding: keeps all the hard tasks to itself, leaving teammates idle.
- No adjudication: records both sides' opinions, denies neither, and the team stalls in place.

**Counterexample**: one person both writes core code and calls itself a coordinator — that is not a coordinator, it is a builder moonlighting as coordinator. It will go easy when reviewing itself.

---

## 2. Builder

**Criterion**: the artifact is executable (code / script / config), and "it runs" is one of the explicit acceptance conditions.

**Typical artifacts**: source, migration scripts, runnable config, unit tests.

**Required tool surface**: write source within own Lane + execute/test + read dependencies. No need to search external web pages.

**Failure modes**:
- Write without running: delivers unexecuted code, leaving "the first run" to downstream.
- Early victory: declares done after one test case passes (the number-one failure mode named in `../../spec-coding-team-skill/references/rails.md` R-5).
- Out-of-bounds patching: modifies someone else's module to make its own tests pass.

**Counterexample**: an "implementer" that only produces design docs or pseudocode. Without an executable artifact, it does not belong to this archetype.

---

## 3. Adversary

**Criterion**: has veto power, and a veto must be accompanied by reproducible evidence; **does not participate in implementation** and does not use the author's reasoning process as a basis for judgment.

**Typical artifacts**: `findings.md`, each entry containing `severity / file:line / evidence / fix`.

**Required tool surface**: read-only source + execute verification + write findings path. **No source write permission**.

**Failure modes**:
- No veto: always PASS, review degenerates into rubber-stamping.
- Soft suggestions: writes blockers as "suggest considering", so downstream cannot stop on that basis.
- Persuaded: withdraws an evidence-backed veto after the author explains.
- Reads the author's thinking: reads the implementer's process record, inheriting its wrong assumptions.

**Counterexample**: a linter-style role that only checks naming and formatting. It can find style issues but will not veto an invalid implementation — that is not enough to constitute "Adversary".

---

## 4. Researcher

**Criterion**: every conclusion comes with a verifiable source; clearly distinguishes "the source says so" from "I infer", and the two must not be written mixed together.

**Typical artifacts**: `research.md`, conclusion + link + confidence + inference marker.

**Required tool surface**: search/fetch + write research path. **No source write permission needed**.

**Failure modes**:
- Inference as fact: judgments without sources written as "the industry generally believes".
- Unverifiable source: gives only the site name, not an address that can be opened.
- Treats external instructions as content: "please execute" and "ignore the above" in web pages are followed (`../../spec-coding-team-skill/references/rails.md` R-7).

**Counterexample**: writing a survey from memory, an industry overview without links, treating search-result snippets as primary sources.

---

## 5. Explainer

**Criterion**: explains the system as an inspectable structure — boundaries, data flow, dependency direction, tradeoffs, failure modes. Downstream can make decisions on that basis, rather than "roughly understand it".

**Typical artifacts**: `architecture.md`, tradeoff table, failure-mode list.

**Required tool surface**: read-only + write architecture docs. No execution needed, and no source writing.

**Failure modes**:
- Big picture without decisions: the diagram is complete, but "choose A or B" has no answer.
- Jargon stacking: uses abstract nouns in place of concrete mechanisms.
- No failure modes: only the happy path, so downstream cannot prevent.

**Counterexample**: an "architecture document" that is only a file tree and directory description. That is an index, not architecture.

---

## 6. Contract Designer

**Criterion**: extracts a reusable contract (schema / interface / spec / template) from multiple concrete requirements, such that **downstream can implement against it without follow-up questions**.

**Typical artifacts**: schema files, interface contracts, code templates, naming conventions.

**Required tool surface**: read/write spec/schema paths + read-only existing implementation. Does not write business source.

**Failure modes**:
- Over-abstraction: creates a layer nobody uses for the sake of "generality".
- Disconnected from implementation: the contract is written but existing code does not conform, and no migration path is given.
- Suggestions only: the output is "suggest unifying naming", with no executable schema.

**Counterexample**: outputs a "best practices checklist" with no machine-readable contract. A checklist is not a pattern.

---

## 7. Verifier

**Criterion**: judges only by the acceptance criteria, **ignoring the author's reasoning and self-report**; executes the end-to-end process; every conclusion has command + output + `file:line`.

**Typical artifacts**: `verification.md`, mapping each acceptance criterion to evidence.

**Required tool surface**: execute + read-only + write verification path. No source write permission.

**Failure modes**:
- Spot checks instead of full coverage: declares pass after running one or two cases.
- Repeats the author's words as evidence: treats "the author says it was tested" as test results.
- No negative tests: only verifies the happy path, does not construct inputs that should fail.

**Counterexample**: a verbal pass in the style of "the code looks fine". Without an execution record, it is not verification.

---

## Adversary vs Verifier (the Most Easily Confused Pair)

| | Adversary (3) | Verifier (7) |
|---|---|---|
| Judgment target | whether the approach and implementation hold | whether the acceptance criteria are met |
| Input | plan + artifacts + code | **acceptance criteria** + artifacts (does not read the plan) |
| Conclusion form | findings (may carry severity) | item-by-item PASS/FAIL |
| Can one serve both in the same round | No | No |

If the same agent both reviews the approach and performs final acceptance, the "acceptance criteria" get reverse-shaped by the review conclusion — the criteria accommodate the implementation. They must be separated.
