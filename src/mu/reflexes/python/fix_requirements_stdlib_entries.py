import re
from pathlib import Path

from ._common import *  # noqa: F401,F403

def fix_requirements_stdlib_entries(req_path: str) -> bool:
    """Remove Python stdlib module names from requirements.txt.

    Models sometimes list stdlib modules (e.g. sqlite3, os, sys, json) in
    requirements.txt. These are not pip-installable and cause the entire
    ``pip install -r requirements.txt`` invocation to fail with "Could not
    find a version that satisfies <module>". When pytest is in the same
    invocation, pytest also fails to install, leaving .venv/bin/pytest absent.
    Generic: stdlib modules are never on PyPI, for any project.
    """
    if not str(req_path).endswith('requirements.txt'):
        return False
    try:
        text = Path(req_path).read_text()
    except OSError:
        return False
    lines = text.splitlines()
    cleaned = []
    removed = []
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith('#'):
            cleaned.append(line)
            continue
        # Strip version specifiers to get bare package name
        pkg_name = re.split(r'[>=<!;\[]', stripped)[0].strip().lower().replace('-', '_')
        if pkg_name in _STDLIB_MODULES:
            removed.append(stripped)
        else:
            cleaned.append(line)
    if not removed:
        return False
    Path(req_path).write_text('\n'.join(cleaned) + '\n')
    print(f"==> [mu-agent] Reflex: removed stdlib entries from requirements.txt: {removed}")
    return True
