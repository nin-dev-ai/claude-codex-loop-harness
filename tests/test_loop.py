import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import loop


class LoopTests(unittest.TestCase):
    def test_schema_fails_closed(self):
        cfg = json.loads((ROOT / '.loop/config.json').read_text())
        cfg['verify_commands'] = []
        with self.assertRaisesRegex(ValueError, 'fail'):
            loop.validate_config(cfg)
        with self.assertRaises(ValueError):
            loop.validate_tasks([{'id': 'TASK-1', 'title': 'x', 'mode': 'build',
                                  'approved': True, 'acceptance': []}])

    def test_selects_only_approved_eligible_tasks(self):
        tasks = [
            {'id': 'TASK-001', 'mode': 'build', 'approved': False, 'depends_on': []},
            {'id': 'TASK-002', 'mode': 'build', 'approved': True, 'depends_on': ['TASK-001']},
            {'id': 'TASK-003', 'mode': 'repair', 'approved': True, 'depends_on': []},
        ]
        self.assertEqual(loop.select_task(tasks, {'completed': []}, 'repair', None)['id'], 'TASK-003')
        with self.assertRaises(ValueError):
            loop.select_task(tasks, {'completed': []}, 'build', None)

    def test_disposable_repo_full_run(self):
        for agent_name in ('codex', 'claude'):
            with self.subTest(agent=agent_name):
                self.run_disposable_repo(agent_name)

    def run_disposable_repo(self, agent_name):
        with tempfile.TemporaryDirectory() as temp:
            repo = pathlib.Path(temp) / 'repo'
            scripts = repo / 'scripts'
            scripts.mkdir(parents=True)
            shutil.copy(ROOT / 'scripts/loop.py', scripts / 'loop.py')
            (scripts / 'verify.sh').write_text('#!/usr/bin/env bash\nset -euo pipefail\ntest -f result.txt\n')
            (repo / '.loop/runs').mkdir(parents=True)
            (repo / '.gitignore').write_text('.loop/runs/\n')
            cfg = json.loads((ROOT / '.loop/config.json').read_text())
            cfg.update(max_attempts=2, timeout_seconds=15, verify_timeout_seconds=15,
                       total_budget_seconds=30, verify_commands=[['test', '-f', 'result.txt']],
                       protected_paths=['scripts/verify.sh'])
            (repo / '.loop/config.json').write_text(json.dumps(cfg))
            (repo / '.loop/tasks.json').write_text(json.dumps([{
                'id': 'TASK-001', 'title': 'Create result', 'mode': 'build',
                'approved': True, 'acceptance': ['result.txt exists'], 'depends_on': []
            }]))
            (repo / '.loop/state.json').write_text(json.dumps({
                'active': None, 'completed': [], 'history': [], 'last_verified_commit': None
            }))
            (repo / '.loop/PROGRESS.md').write_text('# Progress\n')
            bin_dir = pathlib.Path(temp) / 'bin'
            bin_dir.mkdir()
            fake = bin_dir / agent_name
            fake.write_text('#!/usr/bin/env python3\nimport pathlib,sys\n'
                            'path=pathlib.Path.cwd()\n'
                            '(path/"result.txt").write_text("done\\n")\n')
            fake.chmod(0o755)
            def git(*args):
                return subprocess.run(['git', '-C', str(repo), *args], check=True, capture_output=True, text=True)
            git('init', '-b', 'main')
            git('config', 'user.name', 'Harness Test')
            git('config', 'user.email', 'test@example.invalid')
            git('add', '.')
            git('commit', '-m', 'baseline')
            env = dict(os.environ, PATH=f'{bin_dir}:{os.environ["PATH"]}')
            run = subprocess.run([sys.executable, str(scripts / 'loop.py'), 'run',
                                  '--mode', 'build', '--task', 'TASK-001', '--agent', agent_name],
                                 cwd=repo, env=env, capture_output=True, text=True, timeout=40)
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
            state = json.loads((repo / '.loop/state.json').read_text())
            self.assertEqual(state['completed'], ['TASK-001'])
            self.assertTrue(state['last_verified_commit'])
            self.assertTrue(state['last_verified_branch'].startswith(agent_name + '/'))
            self.assertEqual(len(state['history']), 1)
            record = json.loads(pathlib.Path(state['history'][0]['record']).read_text())
            self.assertEqual(record['agent_name'], agent_name)
            self.assertEqual(record['agent']['argv'][0], agent_name)
            if agent_name == 'claude':
                self.assertEqual(record['agent']['argv'][1:4], ['-p', '--permission-mode', 'acceptEdits'])
