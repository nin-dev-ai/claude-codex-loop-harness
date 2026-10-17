#!/usr/bin/env python3
"""Preview and synchronize generated documentation from project know-how."""
import argparse
import datetime as dt
import difflib
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
START, END = '<!-- BEGIN GENERATED -->', '<!-- END GENERATED -->'
MAPPING = {
    'docs/PRD.md': [('Purpose', 'One-Line Purpose'), ('Users', 'Target Users'),
                    ('Features', 'Core Features'), ('Non-functional requirements', 'Non-Functional Requirements'),
                    ('Non-goals', 'Constraints and Non-Goals'), ('Acceptance criteria', 'Acceptance Criteria')],
    'docs/ARCHITECTURE.md': [('Stack', 'Tech Stack'), ('Components and integrations', 'Architecture and Integrations'),
                             ('Constraints', 'Constraints and Non-Goals'), ('Verification', 'Verification Commands')],
    'docs/DESIGN.md': [('Design direction', 'Design Direction'), ('Users', 'Target Users'),
                       ('Features and screens', 'Core Features')],
    '.loop/TASKS.md': [('Initial milestones (planning seeds; not approved implementation tasks)', 'Initial Milestones'),
                       ('Acceptance criteria', 'Acceptance Criteria')],
}

def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()

def sections(value):
    parts = re.split(r'^## (.+)\s*$', value, flags=re.M)
    return {parts[i].strip(): parts[i + 1].strip() for i in range(1, len(parts) - 1, 2)}

def generated_block(value):
    if value.count(START) != 1 or value.count(END) != 1 or value.index(START) > value.index(END):
        raise ValueError('Missing, duplicated, or reversed generated markers')
    return value.split(START, 1)[1].split(END, 1)[0].strip()

def render(old, content):
    generated_block(old)
    before, rest = old.split(START, 1)
    _, after = rest.split(END, 1)
    return before + START + '\n' + content.strip() + '\n' + END + after

def replace_generated(path, content):
    old = path.read_text() if path.exists() else f'# {path.stem}\n\n{START}\n{END}\n'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render(old, content))

def proposal(root=ROOT):
    data = sections((root / 'PROJECT_KNOWHOW.md').read_text())
    state_path = root / '.loop/bootstrap_state.json'
    state = json.loads(state_path.read_text()) if state_path.exists() else {}
    old_sections = state.get('sections', {})
    changed = sorted(key for key in set(old_sections) | set(data) if old_sections.get(key) != data.get(key))
    conflicts, updates = [], {}
    for rel, fields in MAPPING.items():
        path = root / rel
        old = path.read_text() if path.exists() else f'# {path.stem}\n\n{START}\n{END}\n'
        current = generated_block(old)
        expected = state.get('generated_hashes', {}).get(rel)
        if expected and expected != digest(current):
            conflicts.append(f'{rel}: generated section changed since last synchronization')
        content = '\n\n'.join(f'## {label}\n{data.get(source, "TODO: add to PROJECT_KNOWHOW.md")}'
                              for label, source in fields)
        updated = render(old, content)
        if old != updated:
            updates[rel] = updated
    placeholders = [key for key, value in data.items() if re.search(r'\b(TBD|TODO)\b', value, re.I)]
    return data, changed, updates, conflicts, placeholders

def main(argv=None, root=ROOT):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true', help='Apply the displayed proposal after review')
    parser.add_argument('--check', action='store_true', help='Fail when generated documents are out of sync')
    args = parser.parse_args(argv)
    if args.apply and args.check:
        parser.error('--apply and --check are mutually exclusive')
    try:
        data, changed, updates, conflicts, placeholders = proposal(root)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f'Bootstrap error: {exc}', file=sys.stderr)
        return 2
    affected = sorted({path for key in changed for path, fields in MAPPING.items()
                       if key in [source for _, source in fields]})
    print('Changed know-how sections:', ', '.join(changed) or 'none')
    print('Affected documents:', ', '.join(affected) or 'none')
    for rel, new in updates.items():
        old = (root / rel).read_text() if (root / rel).exists() else ''
        print(''.join(difflib.unified_diff(old.splitlines(True), new.splitlines(True),
                                           fromfile=f'a/{rel}', tofile=f'b/{rel}')), end='')
    for item in conflicts:
        print(f'CONFLICT: {item}', file=sys.stderr)
    for item in placeholders:
        print(f'REVIEW: {item}: unresolved placeholder', file=sys.stderr)
    if conflicts:
        return 2
    if args.check:
        return 1 if updates else 0
    if not args.apply:
        print('Preview only. Review the diff, then run --apply to synchronize.')
        return 0
    for rel, content in updates.items():
        (root / rel).write_text(content)
    hashes = {rel: digest(generated_block((root / rel).read_text())) for rel in MAPPING}
    (root / '.loop/bootstrap_state.json').write_text(
        json.dumps({'sections': data, 'generated_hashes': hashes}, indent=2, sort_keys=True) + '\n')
    if updates or changed:
        with (root / '.loop/CHANGELOG.md').open('a') as log:
            log.write(f'\n- {dt.datetime.now(dt.timezone.utc).isoformat()}: synchronized '
                      f'{", ".join(changed) or "no know-how sections"}; updated {", ".join(updates) or "no documents"}.\n')
    print('Synchronization applied. Review and approve detailed tasks before starting the loop.')
    return 0

if __name__ == '__main__':
    sys.exit(main())
