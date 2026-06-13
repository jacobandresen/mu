# Environment hygiene

_‹ [All challenges](README.md)_

- **ID:** `environment-hygiene`
- **Group:** Harness / environment
- **CHALLENGES.md:** item 16
- **Status:** reflex + skill

## What it is

Environment rather than code: system-wide vs Homebrew Python (use a venv), a server port already in use, or an empty session log that leaves no distillable cause.

## Problems affected

- [p2-sqlite](../problems/p2-sqlite.md) — venv/pytest setup
- [p7-flask](../problems/p7-flask.md) — venv + pip install

## Relevant reflexes & mechanisms

- `python-env skill` — venv isolation, pytest version rules, stateless tests
- `fix_missing_venv_rule` — adds a venv setup rule to the Makefile
- `agent.log tee` — empty-log sessions now archive a real cause signature (2026-06-12)

## Residual / notes

The empty-session-log gap was closed by teeing agent.log into the archive, so pre-test failures get a cause instead of '(no test log)'.
