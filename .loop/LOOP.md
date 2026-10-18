# Autonomous Loop Contract
Discover → Plan → Execute → Verify → Iterate → Commit.

- Approve detailed tasks in `.loop/tasks.json` before running. Markdown milestones are planning seeds.
- The controller selects one eligible task for build, repair, or improve and invokes Codex or Claude Code in a task worktree.
- The verifier runs independently of the coding agent.
- A task is committed on its branch only after independent verification succeeds. Pull request review remains a separate human step.
- Never modify protected requirements, tests, CI gates, credentials or deployment configuration just to pass.
- Each attempt is logged with separate stdout, stderr, exit codes, elapsed time, and changed paths. Repeated identical failures and exhausted budgets stop the loop.
- Do not automatically merge or deploy. Create reviewable changes on a task branch.
- Do not claim passing tests prove security or architectural quality.
