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

19. **Syntax error in C# code**
  - Ensure that every opening brace `{` has a corresponding closing brace `}`.

20. **Incorrect function call**
  - A function is expected but a module was called instead; ensure the correct function is referenced.

21. **Indentation issues**
  - Ensure consistent indentation in Python files to avoid syntax errors.

22. **Unused imports**
  - One sentence describing the generic failure mode and what to watch for.
    - Unused imports in Rust can cause build failures; ensure all imports are used or remove them.

23. **String literal not terminated**
  - Ensure all string literals in Go are properly terminated with a closing quote.

24. **Invalid requirement**
  - A package name is expected at the start of a dependency specifier; avoid using paths directly in requirements.

25. **Context overflow in repair loop (400 errors)**
   - When the writer system prompt includes many large skills (vue-ts-env + node-env + test-isolation + no-server + dotnet skills), the combined system + repair context + test output exceeds the model's 6000-token context. Fixed by: (a) using a lean repair system (base + lang-repair only), (b) not re-adding contextual skills already in auto_system, (c) trimming skills loaded for combined stacks. See `_load_repair_skills` and `_contextual_skills`.

26. **tsc lint before npm install**
   - TypeScript files are linted with `tsc --noEmit` immediately after writing, before `npm install` runs. Without `node_modules`, tsc fails with "Cannot find module" which looks like a code bug but is a tooling gap. Fixed by skipping tsc lint when no `node_modules` is found in the file's parent chain. See `_lint_command` in `agent.py`.

27. **Jest "No tests found" with `_test.js` naming**
   - Jest's default `testMatch` requires `.test.js` or `.spec.js` suffixes. The model uses Python-style `_test.js` naming, causing "No tests found." Fixed by: node-env skill guidance on `.test.js` naming + `fix_jest_no_tests_found` reflex that broadens `testRegex` in `package.json`. Fires on "No tests found" in test output.

28. **Vitest globals not enabled**
   - Without `globals: true` in vite.config.ts, calling `test(...)` / `expect(...)` raises `ReferenceError: test is not defined`. Fixed by vue-ts-env skill showing `globals: true` + `fix_vitest_globals` reflex that detects the ReferenceError and adds the config. See `fix_vitest_globals` in `reflexes.py`.

29. **p7 (Flask) model-limited: uses flask_sqlalchemy**
   - The model reaches for Flask-SQLAlchemy ORM even for simple SQLite tasks. flask_sqlalchemy is not installed in the venv, causing `ModuleNotFoundError`. Added guidance to python-writer skill: "Use plain sqlite3, not Flask-SQLAlchemy." Partially mitigated but model still oscillates in test repair.

30. **p10 (dotnet+Vue blog) model-limited**
   - qwen2.5-coder-7b cannot reliably produce a compiling multi-file ASP.NET Core + EF Core app. Each repair iteration reveals a new compile error (CS0841, CS0246, CS1513, CS1022). The repair loop oscillates and exhausts. Hard constraint: encoding the correct Program.cs structure in grounding violates the honesty rule. Verdict: model-limited for this task complexity. A larger model or higher context is needed.

31. **ANSI escape codes inflate repair context**
   - Test runners like Vitest emit ANSI color codes that dramatically inflate the token count of test output passed to the repair model (e.g., 2KB of actual content → 20KB with ANSI). Fixed by stripping ANSI codes in `_read_file_lines` before feeding to model. See `_strip_ansi` in `agent.py`.

## Resolved

- **Missing `fix_sqlite_in_memory` function** — obsolete. AST fixer pass and the orphaned sqlite sensor removed in commit `07717cc`.
- **SQLite persistence across test runs** — addressed via writer‑side test isolation (commit `4dc186c`) instead of a post‑hoc sensor.
- **Git commit command failing on BSD grep** — `sit.sh` no longer uses `grep -Po`; switched to `awk`.
- **Version extraction brittleness** — `sit.sh:102` uses `awk -F'"' '/__version__/ {print $2}' src/mu/__init__.py`.
- **Duplicate dojo cleaning logic** — `sit.sh` now has a single cleanup block guarded by `SKIP_CLEAN`.
- **p8 (Node todo) "No tests found"** — model uses `_test.js` naming; fixed by `fix_jest_no_tests_found` reflex + node-env skill guidance.
- **p9 (Vue todo) TypeScript lint before npm install** — tsc ran before deps installed; fixed by skipping tsc when node_modules absent + `fix_vitest_globals` reflex.

*This file is intended to be updated continuously as new challenges arise.*
