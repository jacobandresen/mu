import re
from pathlib import Path

from ._common import *  # noqa: F401,F403

def fix_python_missing_project_imports(file_path: str) -> bool:
    """Add missing imports for project-local names used but not imported in test files.

    Test files often use `app`, `db`, `client` and similar objects defined in
    the implementation module (app.py, models.py) without importing them. This
    reflex detects usage of names that match symbols exported by sibling .py files
    and adds the missing import.
    General: uses file existence and name matching, not problem-specific patterns.
    """
    if not file_path.lower().endswith('.py'):
        return False
    fp = Path(file_path)
    if not fp.stem.startswith('test_'):
        return False
    try:
        text = fp.read_text()
    except OSError:
        return False
    sibling_modules = list(_sibling_py_sources(file_path))
    if not sibling_modules:
        return False
    # `from mod import mod` for each sibling module name used but not yet imported.
    to_add = [
        f'from {mod} import {mod}'
        for mod in sibling_modules
        if re.search(rf'\b{re.escape(mod)}\b', text)
        and not re.search(rf'(?:import {re.escape(mod)}\b|from {re.escape(mod)}\b)', text)
    ]
    if not to_add:
        return False
    _insert_py_imports(file_path, to_add)
    print(f"==> [mu-agent] Reflex: added {len(to_add)} missing project import(s) to {file_path}: {to_add}")
    return True
