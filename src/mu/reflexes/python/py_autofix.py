import re
from pathlib import Path

from ._common import *  # noqa: F401,F403

def py_autofix(file_path: str) -> bool:
    """Strip unused imports/variables from a Python file (pure-Python autoflake).

    Mirrors the autofixable subset of ``ruff --select=E9,F`` (F401/F841).
    Returns True if the file was processed.
    """
    if not file_path.lower().endswith('.py'):
        return False
    try:
        import autoflake
    except ImportError:
        return False
    try:
        src = Path(file_path).read_text()
        fixed = autoflake.fix_code(src, remove_all_unused_imports=True,
                                   remove_unused_variables=True)
        if fixed != src:
            Path(file_path).write_text(fixed)
    except (OSError, SyntaxError, ValueError):
        return False
    return True
