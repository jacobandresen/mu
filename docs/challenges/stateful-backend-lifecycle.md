# Stateful-backend lifecycle rewrites

_‹ [All challenges](README.md)_

- **ID:** `stateful-backend-lifecycle`
- **Group:** Model ceiling
- **Open list:** [item 13](README.md#open)
- **Status:** not reflex-recoverable

## What it is

A Flask app opens `sqlite3.connect(':memory:')` per request, so each operation gets a fresh empty DB and data never persists — a design error needing an app-architecture rewrite, not a local edit.

## Problems affected

- [p7-flask](../problems/p7-flask.md) — per-operation connect destroys data each call
- [p2-sqlite](../problems/p2-sqlite.md) — connection-scope variants

## Relevant reflexes & mechanisms

- `fix_sqlite_conn_scope` — narrows obvious connection-scope mistakes
- `fix_sqlite_class_missing_init_table` — adds a missing table init

## Residual / notes

The full rewrite (one connection for the app lifetime, or a persisted file) is beyond a 7B repair loop — model ceiling.
