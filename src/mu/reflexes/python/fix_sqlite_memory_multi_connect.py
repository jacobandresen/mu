import re
from pathlib import Path

from ._common import *  # noqa: F401,F403

def fix_sqlite_memory_multi_connect(file_path: str) -> bool:
    """Consolidate multiple sqlite3.connect(':memory:') calls to one persistent connection.

    After fix_sqlite_test_isolation converts paths to ':memory:', classes that open
    a new connection per method each get a fresh empty database — the table created
    in __init__/_create_table doesn't exist in the connection opened by add()/list().

    Detects: self.X stored as ':memory:' AND sqlite3.connect(self.X) in 2+ methods.
    Transforms: adds self._conn = sqlite3.connect(':memory:') in __init__,
                replaces per-method sqlite3.connect(self.X) with conn = self._conn.
    """
    if not file_path.lower().endswith('.py'):
        return False
    try:
        text = Path(file_path).read_text()
    except OSError:
        return False

    if text.count('sqlite3.connect(') < 2:
        return False

    # Find: self.X = ':memory:' (the stored path attribute)
    attr_m = re.search(r"^([ \t]+)(self\.(\w+))\s*=\s*['\"]?:memory:['\"]?$",
                       text, re.MULTILINE)
    if not attr_m:
        return False

    self_attr = attr_m.group(2)    # e.g. self.db_path

    # Confirm the attribute is used in 2+ sqlite3.connect() calls
    connect_re = re.compile(
        r'(\w+)\s*=\s*sqlite3\.connect\(\s*' + re.escape(self_attr) + r'\s*\)'
    )
    if len(connect_re.findall(text)) < 2:
        return False

    # 1. Add self._conn = sqlite3.connect(':memory:') + row_factory after the attr line
    new_text = re.sub(
        r'^([ \t]+)' + re.escape(self_attr) + r"\s*=\s*['\"]?:memory:['\"]?$",
        lambda mo: (
            f"{mo.group(1)}{self_attr} = ':memory:'\n"
            f"{mo.group(1)}self._conn = sqlite3.connect(':memory:')\n"
            f"{mo.group(1)}self._conn.row_factory = sqlite3.Row"
        ),
        text, count=1, flags=re.MULTILINE,
    )

    # 2. Replace per-method connects with self._conn
    new_text = connect_re.sub('conn = self._conn', new_text)

    # 3. Remove lines that immediately follow conn = self._conn that are now
    #    redundant or harmful: row_factory assignments and conn.close() calls.
    #    conn.close() on self._conn would close the persistent connection.
    new_text = re.sub(
        r'(conn = self\._conn\n)([ \t]*)conn\.row_factory\s*=\s*sqlite3\.Row\n',
        r'\1',
        new_text,
    )
    # Remove bare conn.close() calls throughout — the persistent connection
    # must not be closed between method calls.
    new_text = re.sub(r'^[ \t]*conn\.close\(\)\n', '', new_text, flags=re.MULTILINE)

    if new_text == text:
        return False

    Path(file_path).write_text(new_text)
    print(f"==> [mu-agent] Reflex: consolidated :memory: SQLite connections in {file_path}")
    return True
