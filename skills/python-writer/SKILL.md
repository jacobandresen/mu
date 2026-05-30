---
name: python-writer
description: Python code-generation rules — import discipline and module naming. Apply to any Python writing task alongside python-env.
---

- **Import every name you use.** Test files must import the module under test on their first lines. Nothing is in scope unless imported.
- **No synthetic imports.** Never write `import self`, `import __name__`, or any identifier that is not a real stdlib or installable module.
- **Import name = filename.** If the file is `todo.py`, the import is `from todo import …`. Match the stem exactly — never guess `app`, `main`, or `module`.
- **No `if __name__ == "__main__"` guards around setup.** DB connections, table creation, and app objects used by tests must execute at import time so pytest can collect without hitting the guard.
