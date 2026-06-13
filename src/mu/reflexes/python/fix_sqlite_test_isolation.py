import re
from pathlib import Path

from ._common import *  # noqa: F401,F403

def fix_sqlite_test_isolation(file_path: str) -> bool:
    """Replace file-based SQLite paths with ':memory:' in any Python file in a tested project.

    Tests that open a named SQLite file accumulate state across test functions
    and across repair iterations, causing inflated row counts and assertion
    failures. Using ':memory:' gives each connection a fresh database. Fires on
    any .py file (implementation or test) when the project directory contains at
    least one test file — the presence of tests indicates this is a test
    scenario where in-memory SQLite is always correct.
    """
    if not file_path.lower().endswith('.py'):
        return False
    parent = Path(file_path).parent
    has_tests = any(parent.glob('test_*.py'))
    if not has_tests:
        return False
    try:
        text = Path(file_path).read_text()
    except OSError:
        return False
    # Replace SQLAlchemy-style connection strings first (sqlite:///filename.db)
    # SQLAlchemy in-memory URL is 'sqlite:///:memory:', not ':memory:'.
    new_text = re.sub(
        r"sqlite:///[^'\"]*(?:\.db|\.sqlite3?)",
        'sqlite:///:memory:',
        text,
    )
    # Replace quoted .db / .sqlite file paths with ':memory:' for direct sqlite3
    new_text = re.sub(r'''(['"])(?:[^'"]*(?:\.db|\.sqlite3?))\1''', "':memory:'", new_text)
    if new_text == text:
        return False
    Path(file_path).write_text(new_text)
    print(f"==> [mu-agent] Reflex: replaced SQLite file path(s) with :memory: in {file_path}")
    return True
