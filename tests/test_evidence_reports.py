"""Regression coverage for controller-owned evidence and repair feedback."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import loop


class EvidenceReportTests(unittest.TestCase):
    def test_plan_preserves_initial_inputs(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(loop, 'RUNS', Path(temp)):
            task = {'id': 'TASK-001', 'acceptance': ['result exists']}
            cfg = {'verify_commands': [['test', '-f', 'result']], 'protected_paths': ['tests'],
                   'max_attempts': 2, 'total_budget_seconds': 60}
            active = {'branch': 'codex/build-task-001-123', 'worktree': '/worktree', 'started': 'now'}
            path = loop.write_plan(task, cfg, active)
            original = path.read_text()
            task['acceptance'] = ['different']
            self.assertEqual(loop.write_plan(task, cfg, active), path)
            self.assertEqual(path.read_text(), original)
            self.assertEqual(json.loads(original)['task']['acceptance'], ['result exists'])

    def test_aggregate_success_does_not_claim_requirement_pass(self):
        with tempfile.TemporaryDirectory() as temp:
            prefix = Path(temp) / 'TASK-001-attempt-1'
            task = {'id': 'TASK-001', 'acceptance': ['The feature is accessible']}
            record = {'attempt': 1, 'agent': {'exit_code': 0},
                      'verification': {'exit_code': 0}, 'changed_paths': ['result'], 'passed': True}
            loop.write_checks(prefix, task, record, [])
            report = prefix.with_name(prefix.name + '-checks.md').read_text()
            self.assertIn('Independent verification: pass', report)
            self.assertIn('unresolved: The feature is accessible', report)
            self.assertNotIn('pass: The feature', report)
            self.assertIn('TASK-001-attempt-1.json', report)
            self.assertIn('No merge is authorized', report)

    def test_failed_gates_and_feedback_are_explicit(self):
        agent = {'exit_code': 7, 'stdout': '', 'stderr': 'agent unavailable'}
        verify = {'exit_code': 0, 'stdout': 'checks passed', 'stderr': ''}
        text = loop.repair_feedback(agent, verify, [], {'exit_code': 1})
        self.assertIn('Agent failed (exit 7)', text)
        self.assertIn('agent unavailable', text)
        self.assertIn('No changed files', text)
        self.assertIn('Benchmark failed', text)
        with tempfile.TemporaryDirectory() as temp:
            prefix = Path(temp) / 'TASK-001-attempt-2'
            loop.write_checks(prefix, {'id': 'TASK-001', 'acceptance': ['result exists']},
                              {'attempt': 2, 'agent': agent, 'verification': verify,
                               'changed_paths': [], 'passed': False}, ['tests/existing.py'])
            report = prefix.with_name(prefix.name + '-checks.md').read_text()
            self.assertIn('Protected paths: fail', report)
            self.assertIn('Changed files: fail', report)
            self.assertIn('Blocked on failed gates', report)

    def test_successful_feedback_does_not_invent_failures(self):
        result = {'exit_code': 0, 'stdout': 'ok', 'stderr': ''}
        self.assertEqual(loop.repair_feedback(result, result, ['result'], None), 'ok\n')

    def test_resume_restores_previous_failure_in_agent_prompt(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            task = {'id': 'TASK-001', 'mode': 'build', 'title': 'Create result',
                    'acceptance': ['result exists']}
            cfg = {'verify_commands': [['test', '-f', 'result']], 'protected_paths': [],
                   'max_attempts': 2, 'total_budget_seconds': 60,
                   'timeout_seconds': 5, 'verify_timeout_seconds': 5, 'max_output_bytes': 1000}
            state = {'active': {'task': 'TASK-001', 'agent_name': 'codex',
                               'branch': 'codex/build-task-001-123', 'worktree': str(root),
                               'started': 'now', 'started_epoch': loop.time.time(),
                               'attempt': 1, 'previous_failure': None}, 'history': []}
            prior = {'agent': {'exit_code': 7, 'stdout': '', 'stderr': 'specific agent failure'},
                     'verification': {'exit_code': 0, 'stdout': 'ok', 'stderr': ''},
                     'changed_paths': [], 'benchmark': None}
            (root / 'TASK-001-attempt-1.json').write_text(json.dumps(prior))
            result = {'exit_code': 0, 'stdout': 'ok', 'stderr': '', 'elapsed_seconds': 0}
            from types import SimpleNamespace
            with patch.object(loop, 'RUNS', root), patch.object(loop, 'STATE', root / 'state.json'), \
                 patch.object(loop, 'run_logged', return_value=result) as run, \
                 patch.object(loop, 'changed_paths', return_value=[]), \
                 patch.object(loop, 'git', return_value=SimpleNamespace(stdout='')), \
                 patch.object(loop, 'append_progress'):
                self.assertEqual(loop.execute(task, cfg, state, resume=True), 1)
            prompt = run.call_args_list[0].args[0][-1]
            self.assertIn('specific agent failure', prompt)
            self.assertIn('No changed files', prompt)
            self.assertTrue((root / 'TASK-001-attempt-2-checks.md').is_file())
            record = json.loads((root / 'TASK-001-attempt-2.json').read_text())
            self.assertEqual(record['acceptance'], task['acceptance'])
            self.assertEqual(record['protected_path_violations'], [])
            self.assertFalse(record['passed'])
