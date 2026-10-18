#!/usr/bin/env python3
"""Run approved tasks in isolated worktrees with independent verification."""
import argparse
import datetime as dt
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CFG = ROOT / '.loop/config.json'
TASKS = ROOT / '.loop/tasks.json'
STATE = ROOT / '.loop/state.json'
RUNS = ROOT / '.loop/runs'
MODES = {'build', 'repair', 'improve'}
AGENTS = {'codex', 'claude'}

def now():
    return dt.datetime.now(dt.timezone.utc).isoformat()

def load_json(path):
    return json.loads(path.read_text())

def save_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')
    os.replace(temp, path)

def validate_config(cfg):
    for key in ('max_attempts', 'timeout_seconds', 'verify_timeout_seconds', 'total_budget_seconds', 'max_output_bytes'):
        if type(cfg.get(key)) is not int or cfg[key] < 1:
            raise ValueError(f'{key} must be a positive integer')
    commands = cfg.get('verify_commands')
    if not isinstance(commands, list) or not commands:
        raise ValueError('verify_commands must be a nonempty list; verification fails closed')
    for command in commands:
        if not isinstance(command, list) or not command or not all(isinstance(x, str) and x for x in command):
            raise ValueError('each verification command must be a nonempty argv list')
    paths = cfg.get('protected_paths')
    if not isinstance(paths, list) or not all(isinstance(x, str) and x for x in paths):
        raise ValueError('protected_paths must be a list of paths')

def validate_tasks(tasks):
    if not isinstance(tasks, list):
        raise ValueError('tasks.json must contain a list')
    ids = set()
    for task in tasks:
        if not isinstance(task, dict) or not re.fullmatch(r'TASK-\d+', str(task.get('id', ''))):
            raise ValueError('task id must match TASK-<number>')
        if task['id'] in ids:
            raise ValueError(f'duplicate task: {task["id"]}')
        ids.add(task['id'])
        if task.get('mode') not in MODES or type(task.get('approved')) is not bool:
            raise ValueError(f'{task["id"]}: mode or approved invalid')
        if not isinstance(task.get('title'), str) or not task['title'].strip():
            raise ValueError(f'{task["id"]}: title required')
        if not isinstance(task.get('acceptance'), list) or not task['acceptance'] or not all(
            isinstance(x, str) and x.strip() for x in task['acceptance']):
            raise ValueError(f'{task["id"]}: measurable acceptance criteria required')
        if not isinstance(task.get('depends_on', []), list):
            raise ValueError(f'{task["id"]}: depends_on must be a list')
        if task['mode'] == 'improve':
            benchmark = task.get('benchmark')
            if not isinstance(benchmark, dict) or benchmark.get('direction') not in ('min', 'max'):
                raise ValueError(f'{task["id"]}: improve task requires a benchmark and direction')
            if not isinstance(benchmark.get('baseline'), (int, float)) or type(benchmark.get('baseline')) is bool:
                raise ValueError(f'{task["id"]}: numeric benchmark baseline required')
            command = benchmark.get('command')
            if not isinstance(command, list) or not command or not all(isinstance(x, str) and x for x in command):
                raise ValueError(f'{task["id"]}: benchmark command must be argv list')
    for task in tasks:
        if any(dep not in ids for dep in task.get('depends_on', [])):
            raise ValueError(f'{task["id"]}: unknown dependency')

def select_task(tasks, state, mode, task_id):
    completed = set(state.get('completed', []))
    eligible = [t for t in tasks if t['approved'] and t['mode'] == mode and t['id'] not in completed
                and all(dep in completed for dep in t.get('depends_on', []))]
    if task_id:
        eligible = [t for t in eligible if t['id'] == task_id]
    if not eligible:
        raise ValueError('No approved eligible task; check mode, dependencies, and completion state')
    return eligible[0]

def git(*args, cwd=ROOT, check=True):
    return subprocess.run(['git', *args], cwd=cwd, text=True, capture_output=True, check=check)

def run_logged(argv, cwd, timeout, prefix, max_output_bytes):
    prefix.parent.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    out_path, err_path = prefix.with_suffix('.stdout'), prefix.with_suffix('.stderr')
    exceeded = False
    with out_path.open('wb') as out, err_path.open('wb') as err:
        proc = subprocess.Popen(argv, cwd=cwd, stdout=out, stderr=err, start_new_session=True)
        while proc.poll() is None:
            if out_path.stat().st_size + err_path.stat().st_size > max_output_bytes:
                exceeded = True
                break
            if time.monotonic() - started >= timeout:
                break
            time.sleep(0.1)
        if proc.poll() is None:
            import signal
            os.killpg(proc.pid, signal.SIGKILL)
            proc.wait()
        code = 125 if exceeded else (124 if time.monotonic() - started >= timeout else proc.returncode)
    outputs = []
    for suffix in ('.stdout', '.stderr'):
        path = prefix.with_suffix(suffix)
        if path.stat().st_size > max_output_bytes:
            exceeded = True
        outputs.append(path.read_bytes()[-max_output_bytes:].decode(errors='replace'))
    return {'argv': argv, 'exit_code': 125 if exceeded else code, 'stdout': outputs[0],
            'stderr': outputs[1], 'elapsed_seconds': round(time.monotonic() - started, 2),
            'output_limit_exceeded': exceeded}

def changed_paths(worktree):
    result = git('status', '--porcelain', '--untracked-files=all', cwd=worktree)
    paths = []
    for line in result.stdout.splitlines():
        path = line[3:]
        if ' -> ' in path:
            path = path.split(' -> ', 1)[1]
        paths.append(path)
    return paths

def append_progress(task, outcome):
    with (ROOT / '.loop/PROGRESS.md').open('a') as file:
        file.write(f'\n- {now()} {task["id"]} ({task["mode"]}): {outcome}\n')

def execute(task, cfg, state, agent_name='codex', resume=False):
    if state.get('active') and not resume:
        raise ValueError('An interrupted run exists; use --resume')
    if resume:
        active = state.get('active')
        if not active or active['task'] != task['id'] or active.get('agent_name', 'codex') != agent_name:
            raise ValueError('No matching run to resume')
        worktree = Path(active['worktree'])
        if not worktree.is_dir():
            raise ValueError('Saved worktree is missing')
    else:
        branch = f'{agent_name}/{task["mode"]}-{task["id"].lower()}-{int(time.time())}'
        worktree = RUNS / branch.replace('/', '-')
        git('worktree', 'add', '-b', branch, str(worktree), 'HEAD')
        active = {'task': task['id'], 'mode': task['mode'], 'agent_name': agent_name, 'branch': branch,
                  'worktree': str(worktree), 'attempt': 0, 'started': now(),
                  'started_epoch': time.time(), 'previous_failure': None}
        state['active'] = active
        save_json(STATE, state)
    feedback = ''
    while active['attempt'] < cfg['max_attempts']:
        remaining = cfg['total_budget_seconds'] - (time.time() - active['started_epoch'])
        if remaining <= 0:
            break
        active['attempt'] += 1
        attempt = active['attempt']
        save_json(STATE, state)
        prefix = RUNS / f'{task["id"]}-attempt-{attempt}'
        instructions = 'AGENTS.md' if agent_name == 'codex' else 'CLAUDE.md and AGENTS.md'
        prompt = (f'Implement only approved {task["mode"]} task {task["id"]}: {task["title"]}.\n'
                  f'Acceptance: {json.dumps(task["acceptance"])}\n'
                  f'Read {instructions}, PROJECT_KNOWHOW.md, .loop/LOOP.md, .loop/TASKS.md and relevant docs. '
                  f'Do not edit protected paths: {json.dumps(cfg["protected_paths"])}. '
                  'Do not weaken tests, CI, or requirements. Do not merge or deploy. '
                  f'Previous verification feedback:\n{feedback[-6000:]}')
        agent_argv = (['codex', 'exec', '-s', 'workspace-write', '-C', str(worktree), prompt]
                      if agent_name == 'codex' else
                      ['claude', '-p', '--permission-mode', 'acceptEdits', prompt])
        agent = run_logged(agent_argv,
                           worktree, min(cfg['timeout_seconds'], max(1, int(remaining))),
                           prefix.with_name(prefix.name + '-agent'), cfg['max_output_bytes'])
        paths = changed_paths(worktree)
        protected = set(cfg['protected_paths'])
        modified_tests = set(git('diff', '--name-only', 'HEAD', '--', 'tests', cwd=worktree).stdout.splitlines())
        violations = sorted(p for p in paths if p in protected or p.startswith('.github/workflows/')
                            or p in modified_tests)
        if violations:
            feedback = 'Protected files modified: ' + ', '.join(violations)
            verification = {'exit_code': 126, 'stdout': '', 'stderr': feedback, 'elapsed_seconds': 0}
        else:
            remaining = cfg['total_budget_seconds'] - (time.time() - active['started_epoch'])
            if remaining <= 0:
                verification = {'exit_code': 124, 'stdout': '', 'stderr': 'Total budget exceeded', 'elapsed_seconds': 0}
            else:
                verification = run_logged(['bash', 'scripts/verify.sh'], worktree,
                                          min(cfg['verify_timeout_seconds'], max(1, int(remaining))),
                                          prefix.with_name(prefix.name + '-verify'), cfg['max_output_bytes'])
            feedback = verification['stdout'] + '\n' + verification['stderr']
        benchmark_result = None
        if agent['exit_code'] == 0 and verification['exit_code'] == 0 and task['mode'] == 'improve':
            benchmark = task['benchmark']
            benchmark_result = run_logged(benchmark['command'], worktree,
                                          min(cfg['verify_timeout_seconds'], max(1, int(cfg['total_budget_seconds'] -
                                              (time.time() - active['started_epoch'])))),
                                          prefix.with_name(prefix.name + '-benchmark'), cfg['max_output_bytes'])
            try:
                measured = float(benchmark_result['stdout'].strip())
                improved = measured < benchmark['baseline'] if benchmark['direction'] == 'min' else measured > benchmark['baseline']
                if not improved or benchmark_result['exit_code']:
                    raise ValueError('benchmark did not improve')
                benchmark_result['measured'] = measured
            except ValueError:
                verification['exit_code'] = 1
                feedback += '\nBenchmark failed or did not improve against baseline.'
        passed = agent['exit_code'] == 0 and verification['exit_code'] == 0 and bool(paths)
        record = {'task': task['id'], 'attempt': attempt, 'timestamp': now(), 'agent_name': agent_name, 'agent': agent,
                  'verification': verification, 'benchmark': benchmark_result,
                  'changed_paths': paths, 'passed': passed}
        save_json(prefix.with_suffix('.json'), record)
        state.setdefault('history', []).append({'task': task['id'], 'attempt': attempt,
                                                 'passed': passed, 'record': str(prefix.with_suffix('.json'))})
        if passed:
            git('add', '--all', cwd=worktree)
            git('commit', '-m', f'{task["id"]}: {task["title"]}', cwd=worktree)
            state.setdefault('completed', []).append(task['id'])
            state['last_verified_commit'] = git('rev-parse', 'HEAD', cwd=worktree).stdout.strip()
            state['last_verified_branch'] = active['branch']
            state['active'] = None
            save_json(STATE, state)
            append_progress(task, f'verified commit {state["last_verified_commit"]} on {active["branch"]}')
            print(f'Verified and committed on {active["branch"]}. Review before opening a PR.')
            return 0
        fingerprint = hashlib.sha256(feedback.encode()).hexdigest()
        if fingerprint == active['previous_failure'] or violations:
            break
        active['previous_failure'] = fingerprint
        save_json(STATE, state)
    save_json(STATE, state)
    append_progress(task, f'stopped after {active["attempt"]} attempts; inspect {worktree}')
    print(f'Run stopped; worktree retained at {worktree}', file=sys.stderr)
    return 1

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['doctor', 'run', 'validate'])
    parser.add_argument('--mode', choices=sorted(MODES), default='build')
    parser.add_argument('--agent', choices=sorted(AGENTS), help='Coding agent (default: codex)')
    parser.add_argument('--task')
    parser.add_argument('--resume', action='store_true')
    args = parser.parse_args(argv)
    try:
        cfg, tasks, state = load_json(CFG), load_json(TASKS), load_json(STATE)
        validate_config(cfg)
        validate_tasks(tasks)
        if not isinstance(state.get('completed'), list) or not isinstance(state.get('history'), list):
            raise ValueError('state.json requires completed and history lists')
        if args.command == 'validate':
            print('Configuration, task, and state schemas valid')
            return 0
        active_agent = (state.get('active') or {}).get('agent_name', 'codex')
        agent_name = args.agent or (active_agent if args.resume else 'codex')
        for executable in ('git', agent_name):
            if not shutil.which(executable):
                raise ValueError(f'Missing executable: {executable}')
        if args.command == 'doctor':
            print(f'Executables and schemas present. Configure project checks and {agent_name} authentication before running.')
            return 0
        root_changes = [line[3:] for line in git('status', '--porcelain').stdout.splitlines()]
        if any(path not in {'.loop/state.json', '.loop/PROGRESS.md'} for path in root_changes):
            raise ValueError('Commit or stash local changes before running')
        task = select_task(tasks, state, args.mode, args.task)
        return execute(task, cfg, state, agent_name, args.resume)
    except (ValueError, OSError, json.JSONDecodeError, subprocess.CalledProcessError) as exc:
        print(f'Loop error: {exc}', file=sys.stderr)
        return 2

if __name__ == '__main__':
    sys.exit(main())
