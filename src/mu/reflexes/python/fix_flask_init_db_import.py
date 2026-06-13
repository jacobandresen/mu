import re
from pathlib import Path

from ._common import *  # noqa: F401,F403

def fix_flask_init_db_import(file_path: str) -> bool:
    """Remove `init_db` from Flask test imports when app.py doesn't define it.

    Models sometimes write `from app import app, init_db` in test files because
    the test client fixture calls `init_db()`. When `init_db` is not defined in
    app.py, pytest collection fails with ImportError. This reflex removes the
    `init_db` import AND any bare `init_db()` calls from the fixture body.
    Generic: fires whenever the imported symbol is absent in the source module.
    """
    if not file_path.lower().endswith('.py'):
        return False
    try:
        text = Path(file_path).read_text()
    except OSError:
        return False
    # Only act on test files importing init_db from app
    if 'init_db' not in text:
        return False
    # Check if init_db is defined in app.py
    app_py = Path(file_path).parent / 'app.py'
    if not app_py.exists():
        return False
    app_text = app_py.read_text()
    if 'def init_db' in app_text:
        return False  # already defined, nothing to fix
    # Remove init_db from import line: `from app import app, init_db` → `from app import app`
    new_text = re.sub(
        r'(from\s+app\s+import\s+[^,\n]*)(?:,\s*init_db|init_db\s*,\s*)([^\n]*)',
        lambda m: m.group(1).rstrip(', ') + (' ' + m.group(2).strip() if m.group(2).strip() else ''),
        text
    )
    # Also handle: `from app import init_db` as the only import
    new_text = re.sub(r'from\s+app\s+import\s+init_db\s*\n', '', new_text)
    # Remove bare `init_db()` calls
    new_text = re.sub(r'^\s*(?:with\s+app\.app_context\(\)\s*:\s*)?init_db\(\)\s*\n', '', new_text, flags=re.MULTILINE)
    if new_text == text:
        return False
    Path(file_path).write_text(new_text)
    print(f"==> [mu-agent] Reflex: removed init_db import/call from {file_path} (not defined in app.py)")
    return True
