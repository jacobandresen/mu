---
name: task-planner-python
description: Python-specific planning rules for PLAN.md. Loaded alongside task-planner when the goal involves Python, Flask, pytest, or pip.
---

# Python Planning Rules

- Use `python3`, never `python` — the shell subprocess has no aliases.
- Use triple-quoted strings (`"""..."""`) for SQL or multi-line strings passed to `execute()`. Single-quoted strings cannot span multiple lines. Close the call immediately: `conn.execute("""SQL""")` — closing paren on the same line as `"""` or the very next line.
- Lint tool: `ruff` (list in ## Dependencies).

## pytest

- When using pytest with a Makefile, the test recipe **must** use `PYTHONPATH=. pytest`. Without it, `import app` and similar project-root imports fail with `ModuleNotFoundError`.
- Test files **must import every module they use**, including stdlib. If a test uses `sqlite3`, add `import sqlite3`. Undefined names cause ruff to reject the file.
- When the main module has module-level code that initializes state (e.g. creates a DB table on import), add a `conftest.py` that imports the module so state is initialized before tests run.

## Flask REST APIs

- Tests must use only `app.test_client()` — never call `sqlite3.connect()` directly from test files. The app handles its own DB setup. Test by calling POST/GET endpoints on the test client.
