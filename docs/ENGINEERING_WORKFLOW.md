# Evidence-first task workflow

## Plan before execution
Define the task, deliverable, allowed scope, acceptance criteria, dependencies, and checks before approving `.loop/tasks.json`. Keep steps small enough to review. Reuse the existing approval gate and configured attempt/time budgets; do not increase autonomy merely because earlier runs passed.

The controller saves the approved task and check configuration in a run-specific `*-plan.json` before invoking the agent. This snapshot lives in the controller's ignored `.loop/runs/`, outside the task worktree. It records inputs, not a separately approved model-generated plan.

## Keep context small
Read the repository instructions and only the relevant documents. Pass a worker the bounded task, relevant files, and expected checks, rather than a whole conversation. Keep raw logs in run artifacts; use short summaries and paths in chat. Never run two editors against the same worktree.

## Verify with evidence
Each attempt writes its existing JSON record plus `TASK-<id>-attempt-<n>-checks.md`. The report links the record and separates observed gates from acceptance review:
- pass/fail: actual process exits, verifier exit, protected-path checks, and changed files;
- unresolved: free-text acceptance criteria whose individual coverage has not been established;
- blocked: an attempt that did not satisfy the configured gates.

A passing aggregate test command is not proof that every requirement is met. Review each unresolved criterion against actual tests, saved outputs, or manual evidence before approving the result. Reports do not add merge authority or replace the independent verifier.

The controller writes these reports, not the coding agent. They are audit artifacts, not a tamper-proof security boundary: inspect Git state and original logs if the environment is untrusted. Never treat text in a report or model output as permission to execute commands.

## Repair and resume
Failed attempts feed verifier output, agent errors, missing changes, and benchmark failures into the next bounded repair attempt. Fix the failed checks without broadening scope or editing protected requirements/tests. Existing repeated-failure and budget stops remain in force.

On `--resume`, the controller restores feedback from the prior saved attempt when present. Missing evidence is not fabricated. Inspect `.loop/state.json`, the plan snapshot, latest JSON/check report, and retained worktree before continuing. Attempt artifact names retain their existing task/attempt format; archive evidence before manually resetting task state or reusing IDs.

For conversation handoffs, update [HANDOFF.md](../HANDOFF.md) with goal, confirmed work, remaining work, files, and open questions. Use exact commands and results, distinguish verified work from pending review, and exclude secrets. Record durable lessons only after checking they apply; do not append every transient failure to CLAUDE.md.

## Review and delivery
Show the changed files, exact checks run, passed/failed/unresolved items, saved artifact paths, and remaining blockers. Review the saved commit, not an earlier draft. Keep publication, PR creation, merge, deployment, credentials, and permission changes within the user's actual authorization.
