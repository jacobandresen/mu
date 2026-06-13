import re
from pathlib import Path

from ._common import *  # noqa: F401,F403

def fix_python_missing_stdlib_imports(file_path: str) -> bool:
    """Add missing stdlib imports for identifiers used but not imported.

    Scans for `name.` or `name(` usage patterns that require a stdlib import
    and adds the import if it's absent. General: applies to any Python file,
    not specific to any problem domain.
    """
    if not file_path.lower().endswith('.py'):
        return False
    try:
        text = Path(file_path).read_text()
    except OSError:
        return False
    to_add = []
    for name, stmt in _PY_STDLIB_IMPORTS.items():
        # "Already imported" must check whether the *name* is already bound,
        # not just whether a module of that name is imported: keys like
        # 'Flask' come from `from flask import Flask` where the module is
        # lowercase, so a module-keyed check (`^from Flask`) misses the
        # existing `from flask import Flask, ...` and re-adds the import —
        # flake8 F811 redefinition, which the lint gate can't always repair
        # (6 stalled sessions in the 2026-06-12 collection run).
        already = re.search(
            rf'^\s*(?:import\s+{name}\b'                 # import name
            rf'|from\s+\S+\s+import\s+[^\n]*\b{name}\b'  # from mod import …, name
            rf'|import\s+\S+\s+as\s+{name}\b)',          # import mod as name
            text, re.MULTILINE)
        if already or stmt in text:
            continue
        if re.search(rf'\b{name}[\.(]', text):
            to_add.append(stmt)
    if not to_add:
        return False
    lines = text.splitlines()
    insert_at = 0
    for i, line in enumerate(lines):
        if line.startswith(('import ', 'from ')):
            insert_at = i + 1
        elif line and not line.startswith('#') and insert_at > 0:
            break
    for stmt in reversed(to_add):
        lines.insert(insert_at, stmt)
    Path(file_path).write_text('\n'.join(lines) + '\n')
    print(f"==> [mu-agent] Reflex: added {len(to_add)} missing stdlib import(s) to {file_path}: {to_add}")
    return True
