---
name: repair-python
description: Python repair diagnostics — map common error messages to targeted fixes for the repair loop.
---

- `NameError: name 'X' is not defined` — add `from module import X` or `import module` at the top of the file where X is used. If the error is in a module imported by the test file, fix the module, not the test.
- `ERROR collecting test_*.py` — an import or NameError in the traceback prevents collection; trace to the root file (not the test file) and fix the missing import or initialization there first.
- `assert len(items) == N` fails with a much larger count — a persistent SQLite file is accumulating rows across test runs. Rewrite the test to use `sqlite3.connect(":memory:")` or truncate the table in setup.
- `Address already in use` (Flask/uvicorn) — the test command starts a live server. Rewrite tests to use `app.test_client()` so no port is needed.
- `collected 0 items` — no functions named `test_*` were found; pytest only collects functions whose names start with `test_`.
