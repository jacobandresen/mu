# Test isolation design

_‹ [All challenges](README.md)_

- **ID:** `test-isolation-design`
- **Group:** Model ceiling
- **Open list:** [item 12](README.md#open)
- **Status:** partial — reflex enables it when the model writes hooks

## What it is

The model omits `beforeEach/afterEach`, so shared state (a JSON data file, a SQLite DB) leaks across tests and assertions accumulate.

## Problems affected

- [p2-sqlite](../problems/p2-sqlite.md) — shared DB across tests
- [p7-flask](../problems/p7-flask.md) — shared store
- [p8-node-todo](../problems/p8-node-todo.md) — shared JSON data file

## Relevant reflexes & mechanisms

- `fix_js_env_data_file` — points the data file at a per-test path when the model wrote the isolation hooks
- `fix_sqlite_test_isolation` — replaces a shared file path with `:memory:`
- `fix_sqlite_memory_multi_connect` — consolidates per-call `:memory:` connections

## Residual / notes

~50% pass: the reflex can isolate state only when the model wrote the setup/teardown structure; inventing it wholesale is beyond the 7B.
