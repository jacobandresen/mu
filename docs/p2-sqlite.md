# p2-sqlite — Python SQLite todo manager

**Toolchains:** python3 · **Difficulty:** simple

## Problem statement

> write a Python todo list manager that stores todos in a SQLite database.
> Support add, list, and delete operations. Include a test file using
> pytest.

## What it does

A `TodoManager`-style module backed by SQLite with add/list/delete
operations, exercised by a pytest file. The first problem in the set with
real state: the tests create, query, and delete rows, so connection
handling and test isolation matter, not just syntax.

## Major challenges

- **SQLite test isolation** — tests sharing one on-disk database leak rows
  between tests; `:memory:` databases opened per-operation destroy data
  each call ([CHALLENGES.md](../CHALLENGES.md) items 12, 13).
- **Missing/duplicated imports** — the module under test or `sqlite3`
  itself not imported; in 2026-06-12 runs a reflex bug re-added imports
  already bound by `from flask import …`-style lines, stalling every
  session at the lint gate until fixed (items 3, 14).

## Related reflexes

- `fix_sqlite_test_isolation` — replaces a shared file path with
  `:memory:`; `fix_sqlite_memory_multi_connect` — consolidates per-call
  connections; `fix_sqlite_missing_row_factory`, `fix_sqlite_path_unlink`.
- `fix_python_missing_stdlib_imports` (name-binding aware since
  2026-06-12), `fix_python_missing_project_imports`,
  `fix_test_import_module`.
