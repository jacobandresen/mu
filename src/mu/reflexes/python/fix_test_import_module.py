import re
from pathlib import Path

from ._common import *  # noqa: F401,F403

def fix_test_import_module(file_path: str) -> bool:
    """Fix test files that import a module name that doesn't exist on disk."""
    if not file_path.endswith('.py'):
        return False
    stem = Path(file_path).stem.lower()
    if not (stem.startswith('test_') or stem.endswith('_test')):
        return False
    try:
        data = Path(file_path).read_text()
    except OSError:
        return False
    file_dir = Path(file_path).parent
    candidates = [e.name[:-3] for e in file_dir.iterdir()
                  if e.name.endswith('.py') and not e.name.startswith('test_')
                  and not e.name.endswith('_test.py')]
    changed, lines = False, data.splitlines()
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith('from ') and len(stripped.split()) >= 2:
            module_name = stripped.split()[1]
        elif stripped.startswith('import ') and len(stripped.split()) >= 2:
            module_name = stripped.split()[1].split('.')[0]
        else:
            continue
        if (file_dir / (module_name + '.py')).exists():
            continue
        ml = module_name.lower()
        best = next((c for c in candidates
                     if ml.startswith(c.lower()) or c.lower().startswith(ml)
                     or c.lower() in ml or ml in c.lower()), '')
        if best and best != module_name:
            lines[i] = line.replace(module_name, best)
            changed = True
    if not changed:
        return False
    Path(file_path).write_text('\n'.join(lines))
    return True
