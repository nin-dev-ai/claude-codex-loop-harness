# Codex Bootstrap Prompt
Read `PROJECT_KNOWHOW.md` as the single user-authored source of product context. Inspect the existing repository before editing anything.

Update the following dependent files consistently:
- `docs/PRD.md`: user needs, scope, features, non-goals, measurable acceptance criteria.
- `docs/ARCHITECTURE.md`: stack, components, data flow, interfaces, risks and technical constraints.
- `docs/DESIGN.md`: design principles, screens, states and accessibility; mark N/A for backend-only projects.
- `.loop/TASKS.md`: planning narrative; preserve the generated seed section.
- `.loop/tasks.json`: approved, dependency-ordered executable tasks with stable IDs and objective acceptance criteria.
- `.loop/config.json`: propose real verification commands ONLY if they exist and can be run; otherwise leave explicit TODOs.

Rules:
1. Preserve approved decisions and existing custom documentation; present conflicting changes for human review.
2. Do not invent requirements, dependencies or successful test results.
3. Do not modify `PROJECT_KNOWHOW.md` unless asked.
4. Do not weaken tests or verification rules.
5. Summarize all changed files, assumptions, missing inputs and verification readiness.
6. Do not start autonomous implementation until the user approves the generated plan.
