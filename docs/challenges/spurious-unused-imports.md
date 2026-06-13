# Spurious / unused imports

_‹ [All challenges](README.md)_

- **ID:** `spurious-unused-imports`
- **Group:** Degenerate / malformed generation
- **CHALLENGES.md:** item 3
- **Status:** covered by reflexes

## What it is

Imports that don't belong: `import __name__`/`import self` in Python, unused Rust `use` that fails the build, or a re-added import already bound under another name.

## Problems affected

- [p6-rust](../problems/p6-rust.md) — unused `use` causing a build failure
- [p2-sqlite](../problems/p2-sqlite.md) — duplicate `from flask import …` re-added (the 2026-06-12 reflex bug, now fixed)

## Relevant reflexes & mechanisms

- `fix_rust_duplicate_use` — drops a duplicate Rust `use`
- `py_autofix` — autoflake removes unused Python imports
- `fix_python_missing_stdlib_imports` — name-binding-aware: won't re-add a name already bound by `from mod import name`

## Residual / notes

The duplicate-import re-add (flake8 F811) was a reflex bug fixed 2026-06-12 by switching the 'already imported' check from module-name to name-binding.
