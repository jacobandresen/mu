import json
import re
from pathlib import Path
from mu.reflexes.core import _fix_duplicate_decls, fix_literal_newlines, noted

from ._common import *  # noqa: F401,F403

def fix_js_dot_bracket_access(file_path: str, test_output: str = '') -> bool:
    """Remove the stray dot in `expr.[0]` member access.

    A dot directly followed by `[` is never valid JS — computed member access
    is `expr[0]`, and only optional chaining `?.[` legally puts a dot before
    the bracket. Weak models emit chains like `).[0].id`, which Babel rejects
    with "Unexpected token". The fix deletes the dot; `?.[`, spread `...[`,
    and escaped `\\.[` (regex literals) are left alone. Gated on the parser
    error so ordinary files are never touched speculatively.
    """
    if 'Unexpected token' not in test_output:
        return False
    if Path(file_path).suffix.lower() not in ('.js', '.jsx', '.mjs', '.ts', '.tsx'):
        return False
    try:
        text = Path(file_path).read_text()
    except OSError:
        return False
    new_text = re.sub(r'(?<![.?\\])\.(\[)', r'\1', text)
    if new_text == text:
        return False
    Path(file_path).write_text(new_text)
    print(f"==> [mu-agent] Reflex: removed stray dot before '[' in {file_path}")
    return True
