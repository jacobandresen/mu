import re
from pathlib import Path

from ._common import *  # noqa: F401,F403

def fix_sqlite_path_unlink(file_path: str) -> bool:
    """Wrap bare attribute .unlink() calls with Path() in Python test files.

    Models write teardown code like `manager.db_path.unlink(missing_ok=True)`
    but db_path is a plain string, not a Path object, so this raises
    AttributeError. Replace with `Path(manager.db_path).unlink(...)`.
    Only fires on test files to avoid touching production code.
    """
    if not file_path.lower().endswith('.py'):
        return False
    base = Path(file_path).name
    if not (base.startswith('test_') or '_test.' in base):
        return False
    try:
        text = Path(file_path).read_text()
    except OSError:
        return False
    # Match: anything.db_path.unlink( or anything.db.unlink(
    new_text = re.sub(
        r'\b(\w+(?:\.\w+)*\.(?:db_path|db_file|database_path|database|sqlite_path))'
        r'(\.unlink\()',
        r'Path(\1)\2',
        text,
    )
    if new_text == text:
        return False
    # Ensure pathlib is imported
    if 'from pathlib import Path' not in new_text and 'import pathlib' not in new_text:
        new_text = 'from pathlib import Path\n' + new_text
    Path(file_path).write_text(new_text)
    print(f"==> [mu-agent] Reflex: wrapped db_path.unlink() with Path() in {file_path}")
    return True
