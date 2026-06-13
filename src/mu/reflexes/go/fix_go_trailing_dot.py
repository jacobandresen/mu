import re
import shutil
import subprocess
from pathlib import Path

from ._common import *  # noqa: F401,F403

def fix_go_trailing_dot(file_path: str) -> bool:
    """Remove a dangling `.` at the end of a statement that causes 'unexpected ., expected }'.

    LLMs sometimes write a method chain split across lines where the first line
    ends with `).` or `}).` trying to continue a chain, but the chain is never
    completed on the next line (which starts a new statement). Go's parser sees
    the `.` and expects a selector expression, causing a syntax error.

    Detects: a line ending with `).\n` or `}).\n` where the NEXT line does NOT
    start with a letter/identifier (which would complete the chain), and removes
    the trailing `.`.

    General: applies to any .go file with this pattern.
    """
    if not file_path.lower().endswith('.go'):
        return False
    try:
        text = Path(file_path).read_text()
    except OSError:
        return False

    # Pattern: line ends with ). or }). followed by newline
    # Next line must NOT start with a letter (which would complete the chain)
    new_text = re.sub(
        r'([)\}])\.(\n[ \t]*(?:[^a-zA-Z_]|$))',
        r'\1\2',
        text,
    )
    if new_text == text:
        return False
    Path(file_path).write_text(new_text)
    print(f"==> [mu-agent] Reflex: removed dangling trailing '.' in {file_path}")
    return True
