# Top 10 Challenges Observed in the Mu System

The following list tracks the most frequent or significant challenges encountered while running the Mu dojo problems and developing the Mu codebase. This file is updated as new challenges are identified.

1. **Missing `fix_sqlite_in_memory` function**
   - A `NameError` occurred during AST fixers because `fix_sqlite_in_memory` was referenced but not defined. Added a generic sensor to replace file‑based SQLite connections with an in‑memory DB.

2. **Test failures due to missing imports**
   - Generated Python test files often omitted the import of `TodoManager`, causing `NameError`. The `fix_test_import_module` sensor helps but the model still frequently forgets required imports.

3. **Spurious imports and unused symbols**
   - Generated Python files sometimes contain nonsensical imports such as `import __name__`, `import db_path`, `import self`, etc. These cause lint errors and require sensor fixes.

4. **Git commit command failing**
   - The original `git commit` step used `grep -Po` which failed on macOS BSD grep (`grep: invalid option -- P`). Replaced with `awk` for robust version extraction.

5. **Duplicate dojo cleaning logic**
   - `sit.sh` contained two identical blocks for cleaning the `dojo` directory, leading to unnecessary repetition. Consolidated to a single block.

6. **Version extraction brittleness**
   - Extracting the Mu version from `src/mu/__init__.py` needed a reliable method; switched to `awk` to avoid regex incompatibilities.

7. **SQLite persistence across test runs**
   - Using a file‑based SQLite database (`todos.db`) caused data to accumulate across test runs, leading to duplicate entries and failing assertions. Switched to an in‑memory database by default and added a generic `fix_sqlite_in_memory` sensor to ensure test isolation.

8. **Sensor over‑fitting risk**
   - Ensured that added sensors (e.g., SQLite in‑memory) are generic and not tied to a specific dojo problem, adhering to the prime directive of honesty.

9. **Repair loop often exhausted without success**
   - For the SQLite problem, the agent exhausted its repair attempts without fixing the failing tests. Indicates need for better prompt or sensor improvements.

10. **Inconsistent handling of Makefile indentation**
    - Models sometimes emit space‑indented recipes, which break `make`. The `fix_makefile_space_indent` sensor addresses this, but the issue recurs across problems.

*This file is intended to be updated continuously as new challenges arise.*
