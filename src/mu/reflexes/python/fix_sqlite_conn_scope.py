import re
from pathlib import Path

from ._common import *  # noqa: F401,F403

def fix_sqlite_conn_scope(file_path: str) -> bool:
    """Add module-level cursor = conn.cursor() when conn is top-level but cursor is missing.

    LLMs write conn = sqlite3.connect() at module level then write tests that do
    `from main import cursor`, but forget to expose cursor at module level. The fix
    adds cursor = conn.cursor() after the conn line so the test import succeeds.
    Only fires when a sibling test file actually imports cursor from this module.
    General Python pattern: not sqlite-specific beyond detecting sqlite3.connect().
    """
    if not file_path.lower().endswith('.py'):
        return False
    base = Path(file_path).name
    if base.startswith('test_') or '_test.' in base:
        return False
    try:
        text = Path(file_path).read_text()
    except OSError:
        return False

    # Detect: conn = sqlite3.connect(...) at module top level (no leading whitespace)
    conn_m = re.search(r'^(conn)\s*=\s*sqlite3\.connect\([^)]*\)', text, re.MULTILINE)
    if not conn_m:
        return False

    # Skip if cursor is already defined at module level
    if re.search(r'^cursor\s*=', text, re.MULTILINE):
        return False

    # Only fire if a sibling test file imports cursor from this module
    stem = Path(file_path).stem
    parent = Path(file_path).parent
    imports_cursor = False
    for test_file in parent.glob('test_*.py'):
        try:
            ttext = test_file.read_text()
        except OSError:
            continue
        if re.search(rf'from\s+{re.escape(stem)}\s+import\b[^#\n]*\bcursor\b', ttext):
            imports_cursor = True
            break
    if not imports_cursor:
        return False

    # Insert cursor = conn.cursor() after the conn line
    insert_pos = conn_m.end()
    new_text = text[:insert_pos] + '\ncursor = conn.cursor()' + text[insert_pos:]
    Path(file_path).write_text(new_text)
    print(f"==> [mu-agent] Reflex: added module-level cursor = conn.cursor() in {file_path}")
    return True
