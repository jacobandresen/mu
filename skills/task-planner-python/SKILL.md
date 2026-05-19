---
name: task-planner-python
description: Python-specific planning rules. Loaded when goal involves Python, Flask, pytest, or pip.
---

- Use `python3`, never `python`.
- SQL/multi-line strings: use `"""..."""`. Close immediately: `conn.execute("""SQL""")` — paren on same line or next.
- Lint: `ruff`
- pytest in Makefile: recipe must be `PYTHONPATH=. pytest`.
- Test files must import every module they use (including stdlib). Undefined names fail ruff.
- Module-level init (e.g. DB table creation on import): add `conftest.py` that imports the module.
- Flask tests: use `app.test_client()` only — never `sqlite3.connect()` from test files.
