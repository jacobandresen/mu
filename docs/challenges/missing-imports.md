# Missing imports

_‹ [All challenges](README.md)_

- **ID:** `missing-imports`
- **Group:** Model ceiling
- **Open list:** [item 14](README.md#open)
- **Status:** partly patched; still frequent

## What it is

The model uses a symbol it never imported: Python omits the import of the module under test (`NameError`), `ModuleNotFoundError` on `app`/`main`, or a missing C# `using`.

## Problems affected

- [p7-flask](../problems/p7-flask.md) — `ModuleNotFoundError: flask` (run 7 ×3); repair-introduced `Flask(__name__)` without the import
- [p2-sqlite](../problems/p2-sqlite.md) — module-under-test not imported
- [p10-dotnet-vue-blog](../problems/p10-dotnet-vue-blog.md) — missing C# `using` (CS0246)

## Relevant reflexes & mechanisms

- [`fix_python_missing_stdlib_imports`](../../src/mu/reflexes/python/fix_python_missing_stdlib_imports.py) — adds a missing stdlib/framework import (name-binding aware)
- [`fix_python_missing_project_imports`](../../src/mu/reflexes/python/fix_python_missing_project_imports.py) — imports a sibling project module
- [`fix_csharp_missing_using`](../../src/mu/reflexes/csharp/fix_csharp_missing_using.py) — adds a `using` for a CS0246 type found in a sibling file
- [`fix_missing_pip_packages`](../../src/mu/reflexes/python/fix_missing_pip_packages.py) — adds a missing package to requirements

## Residual / notes

Repair-loop edits now get the same write-reflex pass as initial writes, so a repair that introduces an unimported symbol is fixed in the same iteration (2026-06-12).
