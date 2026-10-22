# Context canary and session handoff
- Start every user-facing reply with **Nigel**, without exceptions, including short answers and acknowledgments.
- When the session gets long or earlier work is unclear, first write or update [HANDOFF.md](HANDOFF.md), then tell Nigel about the context uncertainty before continuing work. Record the goal, confirmed completed work, remaining work, key files, and open questions; mark unknowns rather than inventing recall.
- At the start of a new session, read [HANDOFF.md](HANDOFF.md) and verify its status against the repository before resuming.
- Keep this file lean: put long or rarely used guidance in linked documents while preserving its content. The name prefix is a consistency cue, not a reliable test of context retention.

For planning, evidence reports, and bounded repairs, see [the engineering workflow](docs/ENGINEERING_WORKFLOW.md).

# Repository Agent Instructions
1. Read `PROJECT_KNOWHOW.md`, `.loop/LOOP.md`, and `.loop/TASKS.md` before implementing.
2. Read `docs/PRD.md`, `docs/ARCHITECTURE.md`, and `docs/DESIGN.md` when relevant.
3. Only work on the requested task. Do not change protected requirements or verification criteria to force success.
4. Prefer small changes; preserve existing behavior and avoid secrets.
5. Run verification, report actual results, and record unresolved issues.
6. Do not merge, deploy, alter credentials, or perform destructive operations without approval.
7. If requirements are ambiguous, stop rather than inventing high-impact decisions.
8. Keep documentation aligned with implemented behavior, without silently changing approved scope.
