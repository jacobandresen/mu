# p7-flask — Flask REST API with SQLite

**Toolchains:** python3 · **Difficulty:** hard

## Problem statement

> write a Python REST API using Flask with a SQLite backend. Support POST
> /todos (body: JSON with a "task" field) and GET /todos (returns list of
> todos). Include a pytest test file that tests both endpoints. Provide a
> Makefile that installs dependencies with pip and runs pytest.

## What it does

A Flask app exposing POST/GET `/todos` over a SQLite store, tested through
Flask's test client (no live server), with a Makefile handling pip install
and pytest. Combines web routing, persistent state, HTTP status-code
semantics, and pytest fixtures — the densest pure-Python problem in the
set.

## Major challenges

- **Stateful-backend lifecycle** — per-request `sqlite3.connect` against
  `:memory:` destroys the data each call; fixing it needs an architectural
  rewrite beyond a 7B repair loop ([CHALLENGES.md](../CHALLENGES.md)
  item 13).
- **Fixture plumbing** — tests take a `client` fixture that's never
  defined; autoflake then strips the "unused" imports, and a later repair
  edit reintroduces `Flask(__name__)` without the import (`NameError`).
  Root-caused from session transcripts in the 2026-06-12 run 3; repair
  edits now get the write-reflex pass.
- **Status-code details** — POST must return 201; tests assert it.

## Related reflexes

- `fix_missing_flask_client_fixture` — injects the pytest `client`
  fixture when tests use it undefined; `fix_flask_post_missing_201`,
  `fix_flask_test_route_decorators`, `fix_flask_init_db_import`.
- `fix_python_missing_stdlib_imports` (covers `from flask import …`
  binding since 2026-06-12), `fix_missing_pip_packages`, the SQLite
  isolation family shared with [p2](p2-sqlite.md).

## Last measured

_Run 7 — 2026-06-12, 8 h collection, qwen2.5-coder-7b-instruct (ctx 6000)._

| Metric | Value |
|---|---|
| Pass rate | 9/15 |
| Median tokens / run | 12,792 prompt · 856 generated |
| Median repair iters | 1 |
| Heaviest phase | repair |

**Dominant errors this run:**
- **`Makefile: no rule to make target 'test'`** (×7) — the generated Makefile lacks the `test` target the test command invokes; the dominant bucket.
- `ModuleNotFoundError: 'flask'` (×3) — flask absent from the pip install / requirements.
- Outcomes: tests still failing after repair (×3), lint still failing (×2), interrupted (×1).
