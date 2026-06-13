import re
from pathlib import Path

from ._common import *  # noqa: F401,F403

def fix_missing_flask_client_fixture(file_path: str, test_output: str) -> bool:
    """Add a missing @pytest.fixture for Flask test client.

    When a pytest test file uses `client` as a parameter but no fixture named
    `client` is defined, pytest reports "fixture 'client' not found". For Flask
    projects, the correct pattern is to define a fixture that yields a test
    client from `app.test_client()`.

    Fires only when:
    - test output contains "fixture 'client' not found"
    - the file is a test file (starts with test_ or ends with _test.py)
    - the test file has test functions that accept `client` as a parameter
    - no `@pytest.fixture` with name `client` is already defined

    Generic: driven by the error message and test function pattern, not problem-specific.
    """
    if 'fixture \'client\' not found' not in test_output:
        return False
    if not file_path.lower().endswith('.py'):
        return False
    name = Path(file_path).name.lower()
    # Only fire on test files
    if not (name.startswith('test_') or name.endswith('_test.py')):
        return False
    try:
        text = Path(file_path).read_text()
    except OSError:
        return False
    # Only fix if this file has test functions that use `client`
    if not re.search(r'def test_\w+\(client', text):
        return False
    # Only fire for Flask projects: find a sibling .py file that imports Flask
    parent = Path(file_path).parent
    flask_module = None
    for candidate in ['app.py', 'main.py', 'server.py', 'api.py']:
        cand = parent / candidate
        if cand.exists():
            try:
                if 'Flask' in cand.read_text():
                    flask_module = cand.stem  # 'app', 'main', etc.
                    break
            except OSError:
                pass
    if flask_module is None:
        return False
    # Don't add if fixture already exists
    if re.search(r'@pytest\.fixture\s*\ndef client', text):
        return False
    # Determine what app-level reset is needed (reset app._conn if app uses _conn pattern)
    flask_path = parent / (flask_module + '.py')
    has_conn_pattern = flask_path.exists() and '_conn' in flask_path.read_text()
    conn_reset = '    app._conn = None  # force fresh db per test\n' if has_conn_pattern else ''
    conn_teardown = '    app._conn = None  # cleanup\n' if has_conn_pattern else ''
    # Build the preamble (import app if not already there)
    needs_import = (f'from {flask_module} import app' not in text
                    and f'import {flask_module}' not in text)
    preamble = 'import pytest\n'
    if needs_import:
        preamble += f'from {flask_module} import app\n'
    preamble += '\n\n'
    fixture_block = (
        preamble +
        '@pytest.fixture\n'
        'def client():\n'
        '    app.config[\'TESTING\'] = True\n'
        '    app.config[\'DATABASE\'] = \':memory:\'\n' +
        conn_reset +
        '    with app.test_client() as c:\n'
        '        yield c\n' +
        conn_teardown +
        '\n\n'
    )
    # Insert the fixture after all imports but before first test function
    first_test = re.search(r'^def test_', text, re.MULTILINE)
    if first_test:
        insert_pos = first_test.start()
        new_text = text[:insert_pos] + fixture_block + text[insert_pos:]
    else:
        new_text = fixture_block + text
    # Deduplicate `import pytest` lines
    lines = new_text.split('\n')
    seen_pytest_import = False
    deduped = []
    for line in lines:
        if line.strip() == 'import pytest':
            if seen_pytest_import:
                continue
            seen_pytest_import = True
        deduped.append(line)
    new_text = '\n'.join(deduped)
    if new_text == text:
        return False
    Path(file_path).write_text(new_text)
    print(f"==> [mu-agent] Reflex: added Flask client fixture to {file_path}")
    return True
