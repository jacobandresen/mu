import re
from pathlib import Path

from ._common import *  # noqa: F401,F403

def fix_sqlite_missing_row_factory(file_path: str) -> bool:
    """Add conn.row_factory = sqlite3.Row after sqlite3.connect() calls.

    When a Flask app uses `dict(cursor.fetchone())` or `[dict(r) for r in ...]`
    on sqlite3 results but `conn.row_factory = sqlite3.Row` is not set, the
    result is a tuple and `dict(tuple)` raises TypeError. This reflex adds the
    row_factory assignment immediately after each sqlite3.connect() call.
    Generic: fires on any Python file that uses sqlite3.connect without row_factory.
    """
    if not file_path.lower().endswith('.py'):
        return False
    try:
        text = Path(file_path).read_text()
    except OSError:
        return False
    # Only fire if dict() is used on cursor results and row_factory is missing
    if 'row_factory' in text:
        return False  # already set
    if 'sqlite3.connect' not in text:
        return False
    if not re.search(r'\bdict\([^)]*\b(?:fetch|conn|cursor|row|todo|result)', text, re.IGNORECASE):
        # Also check for list comprehension with dict: [dict(r) for r in ...]
        if 'dict(r)' not in text and 'dict(t)' not in text and 'dict(row)' not in text:
            return False
    # Insert `conn.row_factory = sqlite3.Row` after each `sqlite3.connect(...)` assignment
    # Match patterns like: `    self.conn = sqlite3.connect(...)` or `conn = sqlite3.connect(...)`
    def _add_row_factory(m: re.Match) -> str:
        full = m.group(0)
        # Extract indentation and variable name
        indent_m = re.match(r'^([ \t]*)((?:self\.\w+|\w+))\s*=\s*sqlite3\.connect', full)
        if not indent_m:
            return full
        indent, varname = indent_m.group(1), indent_m.group(2)
        return full + f'{indent}{varname}.row_factory = sqlite3.Row\n'

    new_text = re.sub(
        r'[ \t]*(?:self\.\w+|\w+)\s*=\s*sqlite3\.connect\([^\n]*\)\n',
        _add_row_factory,
        text
    )
    if new_text == text:
        return False
    Path(file_path).write_text(new_text)
    print(f"==> [mu-agent] Reflex: added row_factory = sqlite3.Row after sqlite3.connect in {file_path}")
    return True
