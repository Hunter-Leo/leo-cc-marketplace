# Handling Project Overview Queries

When the user asks for a project-level overview — progress summary, status check, bird's-eye view, "where are we", or "what's next":

1. **Read `.dev/blueprint.md`** — this is the single source of truth for project-wide status
2. **For each requirement in `▶ in-progress` status**, also read its `tasks.md` for task-level detail
3. **For each requirement in `⏸ blocked`**, read the `tasks.md` Notes and `init.md` to explain the blocker
4. **Check `.dev/TODO.md`** for unresolved backlog items that may impact progress
5. **Present** a structured summary:

   ```
   ## Project Status

   Blueprint: N requirements | ✅ Done: X | ▶ Active: Y | ⏳ Idle: Z
   Backlog:   TODO.md has W unresolved items

   | Req | Phase | Status | Priority | Dependencies | Next Action |
   |-----|-------|--------|----------|--------------|-------------|
   | 001 user-auth | 07 Execution | ▶ in-progress | P0 | - | T-003: implement login |

   **Recommended focus**: 001-user-auth (highest priority, actively in progress)
   ```

6. If the user then asks about a specific requirement, follow the normal per-requirement flow from the relevant phase document.

Do not answer a project overview query by describing only one requirement — always read the blueprint first. If the blueprint is missing, scan `.dev/` directories for `init.md` files and reconstruct it.
