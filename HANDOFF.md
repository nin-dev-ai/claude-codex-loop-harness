# Session handoff

Update this note before continuing a long session or when earlier context is unclear. Keep it concise, use verified facts, and label unknowns. A new session should reconcile this note with the current branch, diff, tests, and remote status before acting. Never put secrets or unrelated personal context here.

## Goal
Add Nigel's reply-prefix canary and a reliable written handoff workflow and improve the harness with bounded, evidence-first reporting and repair feedback.

## Done
- Added the canary and handoff rules at the top of `CLAUDE.md`.
- Preserved all eight original repository instructions unchanged. They were already concise, so no detail needed moving.
- Added this reusable handoff note with the five required sections.

- Added controller-written plan snapshots and per-attempt check reports, with acceptance criteria explicitly unresolved until evidence is reconciled.
- Added bounded repair feedback for agent errors, no-change attempts, and benchmark failures, including feedback restoration on resume.
- Added a linked workflow guide and regression tests.

## Remaining
- Review the documentation diff and the current PR/CI results before any merge. This note does not imply merge approval or completion.
- For the next task, replace these session-specific entries with that task's verified progress and exact verification results.

## Key files
- [CLAUDE.md](CLAUDE.md): Claude Code canary, handoff rules, and repository instructions.
- [AGENTS.md](AGENTS.md): existing Codex repository instructions.
- [.loop/LOOP.md](.loop/LOOP.md): approval, verification, and review contract.
- [docs/ENGINEERING_WORKFLOW.md](docs/ENGINEERING_WORKFLOW.md): evidence and bounded-repair guidance.
- [scripts/loop.py](scripts/loop.py): controller and reports.
- [tests/test_evidence_reports.py](tests/test_evidence_reports.py): report regression coverage.
- [scripts/verify.sh](scripts/verify.sh): repository verification entry point.

## Open questions
- None about the requested documentation change. Future task scope and permissions must come from the user, not this note.
