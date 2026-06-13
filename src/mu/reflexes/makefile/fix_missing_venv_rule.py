import re
import shutil
from pathlib import Path
from mu.reflexes.core import run_reflexes, fix_tool_call_artifacts

from ._common import *  # noqa: F401,F403

def fix_missing_venv_rule(f: str) -> bool:
    """Add a .venv setup rule when Makefile uses .venv/bin/X but has no .venv: rule.

    A Makefile that calls `.venv/bin/pytest` (or any `.venv/bin/X`) in a
    recipe fails with 'No such file or directory' unless some target creates
    the virtualenv first.  This reflex inserts a `.venv:` target (python3 -m
    venv + pip install) and makes every target that uses .venv/bin depend on it.

    General rule: if you reference a generated directory path in a recipe, you
    must also have a rule that builds it.
    """
    try:
        data = Path(f).read_text()
    except OSError:
        return False

    if '.venv/bin/' not in data:
        return False

    # Check if there's already a rule for .venv
    if re.search(r'(?m)^\.venv\s*:', data):
        return False

    lines = data.splitlines()

    # Find which targets reference .venv/bin/ — add .venv as a prerequisite
    top_re = re.compile(r'^([A-Za-z0-9_./-][A-Za-z0-9_./-]*)\s*:([^=]*)$')
    changed_targets: list[str] = []
    new_lines: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        m = top_re.match(line)
        if m and line[0] not in (' ', '\t'):
            name, prereqs = m.group(1), m.group(2).strip()
            # Look ahead at recipe to see if it uses .venv/bin/
            j = i + 1
            uses_venv = False
            while j < len(lines) and lines[j].startswith('\t'):
                if '.venv/bin/' in lines[j]:
                    uses_venv = True
                j += 1
            if uses_venv and '.venv' not in prereqs:
                deps = ('.venv ' + prereqs).strip()
                new_lines.append(f'{name}: {deps}')
                changed_targets.append(name)
            else:
                new_lines.append(line)
        else:
            new_lines.append(line)
        i += 1

    # Determine requirements file to install
    req_file = 'requirements.txt' if Path(f).parent.joinpath('requirements.txt').exists() else ''
    pip_install = (f'\t.venv/bin/pip install -r {req_file} pytest'
                   if req_file else '\t.venv/bin/pip install pytest')
    venv_block = [
        '',
        '.venv:',
        '\tpython3 -m venv .venv',
        pip_install,
    ]
    new_lines.extend(venv_block)

    Path(f).write_text('\n'.join(new_lines) + '\n')
    return True
