import re
from pathlib import Path

from ._common import *  # noqa: F401,F403

def fix_missing_close_paren(file_path: str, lint_error: str) -> bool:
    """Add missing ) after triple-quoted execute() call."""
    if not file_path.endswith('.py') or 'invalid-syntax' not in lint_error:
        return False
    try:
        data = Path(file_path).read_text()
    except OSError:
        return False
    lines = data.splitlines()
    changed = False
    for i, line in enumerate(lines):
        if line.strip() != '"""':
            continue
        for j in range(i - 1, -1, -1):
            prev = lines[j]
            if '.execute("""' in prev and '""")' not in prev:
                lines[i] = line + ')'
                changed = True
                break
            if '""")' in prev:
                break
    if not changed:
        return False
    Path(file_path).write_text('\n'.join(lines))
    return True
