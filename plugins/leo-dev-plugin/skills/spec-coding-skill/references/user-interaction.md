# User Interaction

## Language

At the start of Phase 01, detect the language the user is communicating in:

- If the user is writing in **English**: use English for all `.dev` documents (default).
- If the user is writing in a **non-English language**: ask once:

  > The `.dev` documents will be written in English by default. Would you like me to use [detected language] instead?

  Use whichever language the user confirms. Apply it consistently to all generated documents for this requirement.

## Interactive Mode

At the start of Phase 01, ask the user once:

> Would you like to proceed interactively? In interactive mode, I'll pause after each phase and after each task during execution for your review.
> Reply **yes** for interactive mode, or **no** to run all phases automatically.

**Interactive mode behavior:**
- Phases 01–06: pause after completing each phase or document, show a summary and ask:
  > ✅ [Phase/document name] complete. Review the output and reply **continue** to proceed, or tell me what to adjust.
- Phase 07 (Execution loop): pause after each task reaches `done`, show a summary and ask:
  > ✅ T-XXX complete. Summary: <what was done>. Continue to the next task? (reply 'continue' or tell me what to adjust)

**Automatic mode behavior:** proceed through all phases without pausing, unless a blocker or ambiguity requires user input.

## Progress Display

At the start of execution and before each phase, display the current progress:

```
[NNN] req-name — Progress
──────────────────────────────
✅ Phase 01 — Initialization
✅ Phase 02 — Prerequisite Tasks
▶  Phase 04 — Implementation Plan   ← now
   Phase 05 — Task Planning
   Phase 06 — Create start-and-resume.md
   Phase 07 — Execution
──────────────────────────────
```

- `✅` = completed
- `▶` = in progress
- (blank) = not-started
- Omit optional phases that were skipped
