import re
import shutil
from pathlib import Path
from mu.reflexes.core import run_reflexes, fix_tool_call_artifacts

from ._common import *  # noqa: F401,F403

def fix_python_venv_cmd(f: str) -> bool:
    """Replace bare 'python' with 'python3' in Makefile venv/pip recipes.

    On macOS and many Linux systems, 'python' is absent or points to Python 2.
    The canonical command is 'python3'.  Only applies inside recipe lines
    (tab-indented) to avoid touching variable assignments or comments.
    """
    if shutil.which('python') and not shutil.which('python3'):
        return False  # system has python but not python3 — no change needed
    try:
        content = Path(f).read_text()
    except OSError:
        return False
    _PY_CMD_RE = re.compile(r'(?m)^(\t.*\b)python( )')
    new_content = _PY_CMD_RE.sub(r'\1python3\2', content)
    if new_content == content:
        return False
    Path(f).write_text(new_content)
    return True
