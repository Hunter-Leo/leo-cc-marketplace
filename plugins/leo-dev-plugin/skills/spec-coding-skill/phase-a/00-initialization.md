# Phase 01 — Initialization

Create the requirement definition document before any planning or coding begins.

**Entry:** A need or requirement has been identified, sized M or larger via [Task Sizing](../shared/00-agent-execution.md#task-sizing).
**Exit:** `init.md` created at `.dev/[NNN]-[req-name]/init.md`, `.dev/blueprint.md` updated with the new requirement.

**Round check:** Before starting, check if `.dev/[NNN]-[req-name]/issues.md` exists. If **yes** (open issues): this is Round N+1 re-entry — read [phase-b/01-round-mechanism.md](../phase-b/01-round-mechanism.md) § Phase 01* first, then update init.md based on open issues.

**XS/S sizing:** complete Pre-flight Checks below, then produce lightweight init.md with inline plan (no separate plan.md/tasks.md). See [Task Sizing](../shared/00-agent-execution.md#task-sizing) for the direct execution flow.

## Step 0 — Requirement Clarity Check

Before Pre-flight Checks, assess requirement clarity:

| Signal | Condition | Action |
|--------|-----------|--------|
| Clear | Specific description, file paths, or spec doc provided | Proceed to Pre-flight Checks |
| Vague | Single sentence, no detail, "vague idea" | Recommend clarification skill. Wait for user response. |

**If vague:** scan available skills for brainstorming/requirements/interview. Recommend best match (see table below). Present user with: "The requirement is still vague. Based on available skills, I recommend `<skill>` because `<reason>`. After completing it, share the output doc path and I'll reference it in `init.md`. Or reply **skip** to proceed directly."

| Situation | Typical best-fit skill |
|-----------|----------------------|
| Has direction, needs design exploration | `superpowers:brainstorming` (or equivalent found in scan) |
| Very vague, many hidden assumptions | `oh-my-claudecode:deep-interview` (or equivalent found in scan) |

Fallback to table above if no matching skills found in scan. Always prefer discovered skills over defaults.

Wait for user confirmation before continuing. If user provides a spec doc path, record it in `init.md` § Spec.

**If clear, or user skips:** proceed to Pre-flight Checks below.

**Note:** This is a suggestion, not a hard gate. The output doc is referenced (path recorded in `init.md`), not merged.

---

## Pre-flight Checks

Before creating `init.md`, complete these two steps (each asked only once per requirement):

1. **Language** — detect the user's communication language and ask if needed (see [shared/00-agent-execution.md](../shared/00-agent-execution.md) § Language)
2. **Interactive mode** — ask the user whether to proceed interactively or automatically (see [shared/00-agent-execution.md](../shared/00-agent-execution.md) § Interactive Mode)

---

## Method Selection

Before writing `init.md`, evaluate which methods apply to this phase.

**Methods tagged for Phase 01:**
- [Term Grilling + ADR](../references/methods/00-term-grilling-and-adr.md) — Term alignment and ADR creation

**Evaluate:**

1. Read the method's `## When to Use` / `## Do Not Use` sections
2. Check for trigger signals in the current spec:
   - Fuzzy/ambiguous terminology (signal words: "robust", "scalable", "efficient", undefined concepts)
   - Hard-to-reverse technical decisions (tech stack, data model, interface contracts)
3. Populate the table:

```
| Method | Phase | Triggers Present? | Apply? | Skip Justification |
|--------|-------|-------------------|--------|--------------------|
| Term Grilling + ADR | 01 | Yes/No | Yes/No | (if No: specific reason) |
```

4. **If Yes**: execute the method after drafting `init.md` (see Term Grilling + ADR doc). Create `.dev/CONTEXT.md` glossary and ADRs as needed.
5. **If No**: record a specific factual justification. Generic "not needed" is invalid.
   Valid examples: "All terminology is concrete and well-defined", "No hard-to-reverse decisions in this requirement"

After Method Selection, proceed to the step below.

---

## Step 1 — Skill & Agent Discovery

Before writing the `# Action Items` section of `init.md`, check for available tools that could help complete this requirement:

1. **Check available skills from session context:**
   - Read the list of available skills provided by the system at session start (visible in the session context / system-reminder)
   - Read each skill's `description` field
   - Match against the current requirement type (UI, data analysis, security, testing, etc.)

2. **Check available OMC agent types from session context:**
   - Read the list of available agent types provided by the system at session start (visible in the session context / system-reminder)
   - Identify agents relevant to the requirement (e.g. `designer` for UI work, `scientist` for data analysis, `security-reviewer` for auth/security)

3. **Add matched skills and agents as optional Prerequisite entries in `# Action Items`:**
   ```
   **Optional tools discovered** (use if relevant):
   - [ ] Use `<skill-name>` to produce `<specific output>` — <one-line reason>
   - [ ] Delegate to `<omc-agent-type>` agent for `<specific subtask>` — <one-line reason>
   ```

4. **Inform the user** which skills/agents were found and briefly explain why they may help.

**Rules:** Read from session context — never hardcode skill or agent names. Only surface tools with clear relevance to the current requirement. All entries are optional.

---

## Output

`.dev/[NNN]-[req-name]/init.md`

Determine `NNN` by listing `.dev/` and using the next available three-digit number (001, 002, …).

## Requirement Name Convention

- Lowercase letters and hyphens only
- Concise and descriptive: `api-analysis`, `code-refactor`, `user-auth`

## Creating init.md

Copy the template from `templates/init.md` to `.dev/[NNN]-[req-name]/init.md`, then fill in each section:

- **Project Stage** — declare `pre-launch` or `live`. See `phase-b/00-start-and-resume.md § Breaking Changes Policy`.
- **Spec** — background, motivation, core problem, usage scenarios
- **Requirements** — functional and technical requirements, interface descriptions
- **Action Items** — prerequisite docs, round artifacts, required docs. Read available skills/agents first (see Skill & Agent Discovery above), then fill the optional tools section.
- **Constitution** — include applicable OOP/SOLID rules from `shared/01-oop-principles.md` and language-specific standards from `shared/02-coding-standards.md`. Keep only the languages and rules that apply.

After creating init.md and its Action Items, proceed to Step 3 — Update Blueprint.

1. **Read** `.dev/blueprint.md` if it exists
2. **Create** `.dev/blueprint.md` if this is the first requirement — use the template from [05-blueprint-management.md](../shared/05-blueprint-management.md)
3. **Add a row** for this new requirement with:
   - Phase: `01 Init`
   - Status: `⏳ pending`
   - Priority: inferred from the requirement urgency (P0/P1/P2)
   - Dependencies: inferred from the requirement context
4. **Update** the Progress Summary section to reflect the new total

If `.dev/TODO.md` does not exist, copy it from `templates/TODO.md`.

Then inform the user:

✅ `init.md` created at `.dev/[NNN]-[req-name]/init.md`

✅ Blueprint updated at `.dev/blueprint.md`

Review the documents and either edit them directly or tell me what to change.
Reply **yes** or **continue** to begin executing the Action Items.
