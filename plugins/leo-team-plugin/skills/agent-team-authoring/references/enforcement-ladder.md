# Three Layers of Enforcement

> Where the same rule is written determines whether it is a "suggestion" or a "constraint".
> Choosing the wrong layer is the most common structural error in team design — costlier than writing the wrong content, because it makes people believe a safeguard already exists.

## Measured Data Point

A phase gate written as a text requirement in a 1648-line SKILL.md ("must obtain user confirmation before entering the next phase") hit **0/4** in four trigger tests.

The conclusion is not "not written prominently enough", but: **text gates in long documents get diluted by context to near zero**. The model has read it, but will not recall it at the actual decision point. For it to take effect, the layer must be changed.

---

## Three Layer Definitions

### L1 Text Rules

| Dimension | Description |
|---|---|
| **Guarantees** | the reader will know once they read it; strongest at explaining "why" |
| **Does not guarantee** | recall at the decision point; execution |
| **Cost** | extremely low: a few lines |
| **Failure mode** | the longer the document, the more it fails; ignored preferentially when it "seems unrelated" to the current task |
| **Applies to** | principles, tradeoffs, reasons, judgment criteria |

### L2 Document Structure

| Dimension | Description |
|---|---|
| **Guarantees** | structure exists; missing fields visible to the eye/script; cross-file references traceable |
| **Does not guarantee** | field semantics correct; the filler did not phone it in |
| **Cost** | low: define schema, templates, required sections |
| **Failure mode** | fields filled but empty/placeholder ("to be added"); templates copied and no longer maintained |
| **Applies to** | role card 11 fields, return contract, snapshot four elements, task table column structure |

### L3 hook / scripts

| Dimension | Description |
|---|---|
| **Guarantees** | violation fails: reject write, reject stop, reject state transition |
| **Does not guarantee** | intent reasonable (it can block "illegal", not judge "foolish") |
| **Cost** | high: write code, handle false positives, maintain, cross-platform |
| **Failure mode** | overly strict rules lead to bypass; hook errors treated as noise; scripts out of sync with docs |
| **Applies to** | path boundaries, state transition validity, return format completeness, completion judgment |

---

## Which Layer: Decision Table

| Constraint | Layer | Reason |
|---|---|---|
| who can write which paths | **L3** | out-of-bounds writes are irreversible, must reject beforehand |
| whether a state transition is valid | **L3** | LLMs rationalize skipping steps; must be decided by deterministic code |
| whether completion holds | **L3** | "looks complete" is the most expensive misjudgment; script evidence required |
| whether the return contains verdict | **L3** | a return missing fields cannot be consumed downstream |
| whether two roles' lanes intersect | **L3** | a static check before dispatch, one script call |
| team size cap | **L2** | table structure + self-check list; over-limit can be manually vetoed |
| whether role card fields are complete | **L2** | templates guarantee structure; semantics still need human judgment |
| whether DEAD_ENDS exists | **L2** | file existence is script-checkable, but content quality relies on humans |
| field names of the handoff contract | **L2** | field names must be globally consistent, fixed by templates |
| why decompose this way | **L1** | not machine-decidable, can only rely on reason text |
| tradeoffs and priorities | **L1** | context-dependent |
| what counts as a "contaminated second opinion" | **L1** | semantic boundary, cannot be scripted |
| when to escalate to the user | **L2 + L1** | trigger conditions in the role card (structure), severity judgment by text |

## An Actionable Decision Order

```text
1. Would violating this rule cause irreversible damage (overwrite, loss, fabrication)?
   Yes → L3
2. Can this rule be expressed as "field exists / file exists / sets intersect"?
   Yes → L2
3. Everything else is L1, and do not pretend it will be executed.
```

## Common Misplacements

| Misplacement | Symptom | Fix |
|---|---|---|
| path boundary written only as text | "must not modify other modules" written in the role card body | register the globs as the work unit (`flow.sh add-unit --files`) and take the claim (`flow.sh claim --files`); `PreToolUse` denies writes outside `claim.files` |
| completion judgment written only as text | "mark complete after tests pass" | change to commands + exit codes in Done criteria |
| state machine handed to the LLM | "please judge the next step based on current progress" | write a state transition table + validation script |
| afraid to use L3 for anything | all rules live in docs, zero scripts | at minimum push down paths and state transitions |
| using L3 for everything | every suggestion becomes a hook | false positives accumulate, hooks get ignored; fall back to L2/L1 |

## Layer and Auditability

L1 rules **cannot prove they were ever executed** after an incident; L2 can prove "the field was filled"; L3 can prove "it was checked at the time and a result was given".

Therefore: **any constraint you want to be able to hold someone accountable for afterward should not remain only at L1.**
