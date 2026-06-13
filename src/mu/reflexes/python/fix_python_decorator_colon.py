import re
from pathlib import Path

from ._common import *  # noqa: F401,F403

def fix_python_decorator_colon(file_path: str) -> bool:
    """Remove spurious trailing colon from Python decorator lines.

    Models occasionally write `@decorator(...):` which is a SyntaxError —
    decorators must not end with a colon (the colon belongs on the def/class
    line below, not the decorator). This is a general error on any decorator,
    not specific to Flask.
    """
    if not file_path.lower().endswith('.py'):
        return False
    try:
        text = Path(file_path).read_text()
    except OSError:
        return False
    pattern = re.compile(r'^(@\w[\w.]*\(.*\))\s*:\s*$', re.MULTILINE)
    new_text, count = pattern.subn(r'\1', text)
    if not count:
        return False
    Path(file_path).write_text(new_text)
    print(f"==> [mu-agent] Reflex: removed {count} spurious colon(s) from decorator(s) in {file_path}")
    return True
