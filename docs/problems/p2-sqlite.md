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
  each call (challenges [test-isolation-design](../challenges/test-isolation-design.md), [stateful-backend-lifecycle](../challenges/stateful-backend-lifecycle.md)).
- **Missing/duplicated imports** — the module under test or `sqlite3`
  itself not imported; in 2026-06-12 runs a reflex bug re-added imports
  already bound by `from flask import …`-style lines, stalling every
  session at the lint gate until fixed (items 3, 14).

## Related reflexes

- [`fix_sqlite_test_isolation`](../../src/mu/reflexes/python/fix_sqlite_test_isolation.py) — replaces a shared file path with
  `:memory:`; [`fix_sqlite_memory_multi_connect`](../../src/mu/reflexes/python/fix_sqlite_memory_multi_connect.py) — consolidates per-call
  connections; [`fix_sqlite_missing_row_factory`](../../src/mu/reflexes/python/fix_sqlite_missing_row_factory.py), [`fix_sqlite_path_unlink`](../../src/mu/reflexes/python/fix_sqlite_path_unlink.py).
- [`fix_python_missing_stdlib_imports`](../../src/mu/reflexes/python/fix_python_missing_stdlib_imports.py) (name-binding aware since
  2026-06-12), [`fix_python_missing_project_imports`](../../src/mu/reflexes/python/fix_python_missing_project_imports.py),
  [`fix_test_import_module`](../../src/mu/reflexes/python/fix_test_import_module.py).

## Last measured

_Run 7 — 2026-06-12, 8 h collection, qwen2.5-coder-7b-instruct (ctx 6000)._

| Metric | Value |
|---|---|
| Pass rate | 9/15 |
| Median tokens / run | 16,894 prompt · 1,092 generated |
| Median repair iters | 6 |
| Heaviest phase | repair |

**Dominant errors this run:**
- SQLAlchemy ORM misuse — `type object 'Todo' has no attribute '__table__'`, `undefined name 'declarative_base'` (×3, ×2): model mixes declarative-base setup incorrectly.
- `'TodoManager' object has no attribute '_conn'` (×2) — connection attribute set on a different path than it's read.
- Outcomes: tests still failing after repair (×5), lint still failing after repair (×1).
