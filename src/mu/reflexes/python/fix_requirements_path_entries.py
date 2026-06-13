import re
from pathlib import Path

from ._common import *  # noqa: F401,F403

def fix_requirements_path_entries(f: str) -> bool:
    """Remove path-style entries from requirements.txt.

    Models sometimes write executable paths (e.g. '.venv/bin/pytest') into
    requirements.txt instead of package names. pip rejects these with
    'Expected package name at the start of dependency specifier'.
    Any line that starts with '.' or '/' (a path, not a package name) is stripped.
    """
    if not f.endswith('requirements.txt'):
        return False
    try:
        text = Path(f).read_text()
    except OSError:
        return False
    lines = text.splitlines(keepends=True)
    cleaned = [ln for ln in lines if not ln.lstrip().startswith(('.', '/'))]
    if len(cleaned) == len(lines):
        return False
    Path(f).write_text(''.join(cleaned))
    print(f"==> [mu-agent] Reflex: removed {len(lines) - len(cleaned)} path entry/entries from {f}")
    return True
