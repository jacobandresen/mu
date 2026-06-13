import re
from pathlib import Path

from ._common import *  # noqa: F401,F403

def fix_flask_test_route_decorators(file_path: str) -> bool:
    """Strip @app.route decorators from pytest test files.

    Models sometimes write Flask route handlers (`@app.route(...)`) inside test
    files that also import the Flask app. This causes two problems:
    1. "View function mapping is overwriting an existing endpoint function" — the
       test file re-registers routes already defined in app.py.
    2. The decorated functions are treated as Flask handlers, not pytest tests,
       so the `client` fixture parameter is misunderstood.

    Fires only on files whose name starts with `test_` or ends with `_test.py`.
    Generic: driven by the conflict pattern, not by any specific project.
    """
    if not file_path.lower().endswith('.py'):
        return False
    name = Path(file_path).name.lower()
    if not (name.startswith('test_') or name.endswith('_test.py')):
        return False
    try:
        text = Path(file_path).read_text()
    except OSError:
        return False
    if 'app.route' not in text:
        return False
    # Remove @app.route(...) lines (possibly multi-line with methods=[...])
    new_text = re.sub(r'@app\.route\([^\)]*\)\n', '', text)
    if new_text == text:
        return False
    Path(file_path).write_text(new_text)
    print(f"==> [mu-agent] Reflex: stripped @app.route decorators from test file {file_path}")
    return True
