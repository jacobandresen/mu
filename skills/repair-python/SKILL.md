---
name: repair-python
description: Python repair diagnostics — map common error messages to targeted fixes for the repair loop.
---

- `NameError: name 'X' is not defined` — add `from module import X` or `import module` at the top of the file where X is used. If the error is in a module imported by the test file, fix the module, not the test.
- `undefined name 'X'` in a test file — `X` is defined in the implementation but not imported into the test. Add `from module import X` at the top of the test file, where `module` is the filename (without `.py`) that defines `X`. Example: if `app.py` defines `db`, add `from app import db` to the test.
- `ERROR collecting test_*.py` — an import or NameError in the traceback prevents collection; trace to the root file (not the test file) and fix the missing import or initialization there first.
- `assert len(items) == N` fails with a much larger count — a persistent SQLite file is accumulating rows across test runs. Rewrite the test to use `sqlite3.connect(":memory:")` or truncate the table in setup.
- `OperationalError: no such table: X` — each `sqlite3.connect(':memory:')` call creates a **new empty database**. If a class opens a fresh connection in every method, the table created in `__init__`/`_create_table` does not exist in the connection opened by `add()`/`list()`/`delete()`. Fix: store one persistent connection as `self._conn = sqlite3.connect(':memory:')` in `__init__` (with `self._conn.row_factory = sqlite3.Row`), then use `conn = self._conn` in every other method instead of calling `sqlite3.connect()` again.
- `Address already in use` (Flask/uvicorn) — the test command starts a live server. Rewrite tests to use `app.test_client()` so no port is needed.
- `collected 0 items` — no functions named `test_*` were found; pytest only collects functions whose names start with `test_`.
