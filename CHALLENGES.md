# Challenges Observed in the Mu System

Tracks the most frequent or significant challenges encountered while running the Mu dojo problems and developing the Mu codebase. Updated as new challenges are identified and old ones are resolved.

## Open

1. **Test failures due to missing imports**
   - Generated Python test files often omit the import of the module under test (e.g. `TodoManager`), causing `NameError`. `fix_test_import_module` (`src/mu/sensors.py:88`, invoked from `agent.py:688`) patches the common case, but the model still frequently forgets required imports.

2. **Spurious imports and unused symbols**
   - Generated Python files sometimes contain nonsensical imports such as `import __name__`, `import db_path`, `import self`. No dedicated sensor; cleanup relies on `py_autofix` (autoflake).

3. **Sensor over‑fitting risk**
   - Added sensors must remain generic and not tied to a specific dojo problem, per the prime directive of honesty. Easy to violate when a single problem keeps failing.

4. **Repair loop exhaustion**
   - The repair loop can still exhaust attempts without fixing the failing tests. Partially mitigated: `repair_loop` now receives the plan's source/test files as context (commit `07717cc`), and syntax‑breaking edits are rolled back (commit `e3fc108`). Further prompt/sensor improvements likely still needed.

5. **Inconsistent handling of Makefile indentation**
   - Every Makefile recipe line must begin with a literal TAB character. Spaces — even one — make `make` emit "missing separator" and abort. When a plan writes a Makefile, the description must state explicitly that recipe lines are tab-indented, and the writer must not convert tabs to spaces.

6. **Missing positional argument in format string**
  - Ensure that the number of placeholders in a format string matches the number of arguments provided.

7. **Build target inconsistency**
  - Plans frequently name an entry-point target the build file does not actually define; require the planner to spell out every target the test command invokes.

8. **Database state leaks across runs**
  - Tests that interact with a database may leave behind data from previous test executions, causing subsequent tests to fail due to unexpected data. Ensure each test sets up and tears down the database in isolation.

9. **ModuleNotFoundError on importing 'app'**
  - Ensure the module name matches the file structure and is correctly referenced in imports.

10. **Incorrect format string usage**
  - Ensure that format strings in `println!` and similar macros use string literals for placeholders.

11. **Missing database import**
  - Ensure all necessary libraries are imported before use to avoid runtime errors.

12. **Port already in use**
  - Ensure the port specified for the HTTP server is not already occupied by another process. Check and free up the port before running the server again.

13. **Syntax error in SQL query**
  - Ensure proper indentation and correct use of the backslash for line continuations in SQL queries.

14. **Line continuation character**
  - Ensure that line continuations are used correctly in Python scripts to avoid syntax errors.

15. **Duplicate method definition**
  - Ensure that no methods are defined more than once in a class.

16. **Syntax error in Rust code**
  - Unexpected closing delimiters like `{` and `}` require matching opening delimiters. Ensure all brackets are properly opened and closed.

17. **Top-level statements must precede namespace and type declarations**
  - Top-level statements in C# must appear before any namespaces or types; ensure they are placed correctly to avoid syntax errors.

18. **Syntax error in Python code**
  - Ensure proper indentation and correct use of colons for function definitions and control structures.

## Resolved

- **Missing `fix_sqlite_in_memory` function** — obsolete. AST fixer pass and the orphaned sqlite sensor removed in commit `07717cc`.
- **SQLite persistence across test runs** — addressed via writer‑side test isolation (commit `4dc186c`) instead of a post‑hoc sensor.
- **Git commit command failing on BSD grep** — `sit.sh` no longer uses `grep -Po`; switched to `awk`.
- **Version extraction brittleness** — `sit.sh:102` uses `awk -F'"' '/__version__/ {print $2}' src/mu/__init__.py`.
- **Duplicate dojo cleaning logic** — `sit.sh` now has a single cleanup block guarded by `SKIP_CLEAN`.

*This file is intended to be updated continuously as new challenges arise.*
