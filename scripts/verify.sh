#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
python3 scripts/bootstrap.py --check
python3 scripts/loop.py validate
python3 - <<'PYCODE'
import json, subprocess, sys
from pathlib import Path
cfg = json.loads(Path('.loop/config.json').read_text())
commands = cfg.get('verify_commands', [])
if not commands:
    print('ERROR: No verification commands configured. Fail closed.', file=sys.stderr)
    sys.exit(2)
for command in commands:
    if not isinstance(command, list) or not command or not all(isinstance(x,str) and x for x in command):
        print('ERROR: verification commands must be nonempty argv lists', file=sys.stderr)
        sys.exit(2)
    print('VERIFY:', command, flush=True)
    try:
        subprocess.run(command, check=True, timeout=cfg.get('verify_timeout_seconds',300))
    except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        print(f'ERROR: verification failed: {exc}', file=sys.stderr)
        sys.exit(1)
PYCODE
