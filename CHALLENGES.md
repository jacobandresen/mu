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

32. **p8 (Node todo) stochastic: test isolation design**
   - The model sometimes writes test files without `beforeEach/afterEach` cleanup. When tests run sequentially without isolation, `test('lists todos')` expects `[]` but the previous `addTodo` test left data in `todo.json`. The repair model then targets `index.js` (not the test file), mangling it with duplicate declarations. Fixed partially: `fix_js_env_data_file` converts module-level env-var constants to getter functions (enabling `process.env.TODO_FILE`-based isolation when the model does write proper `beforeEach/afterEach`). The node-env skill now shows the correct isolation pattern and getter function approach. Passes ~50% of runs when model follows the skill; fails when it doesn't.

25. **Context overflow in repair loop (400 errors)**
   - When the writer system prompt includes many large skills (vue-ts-env + node-env + test-isolation + no-server + dotnet skills), the combined system + repair context + test output exceeds the model's 6000-token context. Fixed by: (a) using a lean repair system (base + lang-repair only), (b) not re-adding contextual skills already in auto_system, (c) trimming skills loaded for combined stacks. See `_load_repair_skills` and `_contextual_skills`.

26. **tsc lint before npm install**
   - TypeScript files are linted with `tsc --noEmit` immediately after writing, before `npm install` runs. Without `node_modules`, tsc fails with "Cannot find module" which looks like a code bug but is a tooling gap. Fixed by skipping tsc lint when no `node_modules` is found in the file's parent chain. See `_lint_command` in `agent.py`.

27. **Jest "No tests found" with `_test.js` naming**
   - Jest's default `testMatch` requires `.test.js` or `.spec.js` suffixes. The model uses Python-style `_test.js` naming, causing "No tests found." Fixed by: node-env skill guidance on `.test.js` naming + `fix_jest_no_tests_found` reflex that broadens `testRegex` in `package.json`. Fires on "No tests found" in test output.

28. **Vitest globals not enabled**
   - Without `globals: true` in vite.config.ts, calling `test(...)` / `expect(...)` raises `ReferenceError: test is not defined`. Fixed by vue-ts-env skill showing `globals: true` + `fix_vitest_globals` reflex that detects the ReferenceError and adds the config. See `fix_vitest_globals` in `reflexes.py`.

29. **p7 (Flask) model-limited: per-operation sqlite3 connection lifecycle**
   - Even after updating python-writer skill to forbid SQLAlchemy (which stopped the model using SQLAlchemy), the model generates per-operation sqlite3 connections: each method does `with sqlite3.connect(self.db_path) as conn:`. When `fix_sqlite_test_isolation` replaces `'todos.db'` with `':memory:'`, each method call sees a fresh empty database — data inserted in `add_task` is destroyed on return, `get_tasks` sees nothing. The repair model then "fixes" it by reverting to file-based, causing state accumulation. The correct fix requires an architectural rewrite (persistent `self.conn` in `__init__`, or per-test temp-file fixture), which is beyond the 7B model's repair loop capability. Model-limited; a larger model is needed.

30. **p10 (dotnet+Vue blog) model-limited**
   - qwen2.5-coder-7b cannot reliably produce a compiling multi-file ASP.NET Core + EF Core app. Each repair iteration reveals a new compile error (CS0841, CS0246, CS1513, CS1022). The repair loop oscillates and exhausts. Hard constraint: encoding the correct Program.cs structure in grounding violates the honesty rule. Verdict: model-limited for this task complexity. A larger model or higher context is needed.

31. **ANSI escape codes inflate repair context**
   - Test runners like Vitest emit ANSI color codes that dramatically inflate the token count of test output passed to the repair model (e.g., 2KB of actual content → 20KB with ANSI). Fixed by stripping ANSI codes in `_read_file_lines` before feeding to model. See `_strip_ansi` in `agent.py`.

33. **p7 (Flask) test pattern mismatch: ORM method vs HTTP client assertions**
   - Model writes test calling `todo_manager.add_todo({'task': 'x'})` but then asserts `response.status_code == 201` — treating an ORM return value as an HTTP response. `add_todo()` returns None; `None.status_code` raises AttributeError. The repair model targets `app.py` (making it return an HTTP response object) rather than rewriting the test to use Flask's `app.test_client()`. Repair loop stalls after 2 identical edits. Model-limited: the architectural mismatch requires rewriting the test file, which the repair model doesn't attempt.

34. **Writer 400 Bad Request on large skill system prompts**
   - When 3+ skills are loaded (vue-ts-env + node-env + makefile-writer = ~12KB), the first writer call gets HTTP 400 from LM Studio. The retry with lean system (no skills, ~800 chars) succeeds. Root cause unclear (not token overflow by estimate); may be a LM Studio model-specific system-prompt size limit. Fixed: outer retry uses `_build_autonomous_system` without skills; `Session.run()` nudges on prose even when watch_file is set (previously returned False immediately).

35. **Lean-system retry writes files to wrong paths**
   - The lean retry (no skills) often writes to subdirectories (e.g., `src/vite.config.ts`, `backend/Program.cs`) instead of the plan-specified path. Fixed: (a) file relocation runs after both first attempt and retry; (b) `reapply()` deletes stale `.cs` files from unexpected subdirectories (skipping `obj/`, `bin/`) to prevent duplicate class compilation errors.

36. **`vitest` in package.json scripts runs in watch mode**
   - `"test": "vitest"` starts Vitest in interactive watch mode; never exits. The test runner hangs and eventually times out, masking a passing test suite. Fixed: `fix_vitest_watch_mode` replaces `"vitest"` with `"vitest run"` in package.json scripts.

37. **Missing `vue` peer dependency**
   - Lean-system retry writes package.json with `@vitejs/plugin-vue` and `@vue/test-utils` but omits `vue` itself. `@vue/compiler-sfc` then fails to find its companion module at runtime. Fixed: `fix_vue_missing_package` reflex adds `"vue": "^3.4.0"` whenever `@vue/...` packages are present but `vue` is absent.

38. **Makefile escape artifacts: `\n`, `\t`, `\@`, `\$(npm)`**
   - Lean-system retry writes Makefiles with literal `\n` (newlines as escape sequences), `\@` (backslash before silent @), and `\$(npm)` (escaped dollar in command substitution). Each breaks `make` in a different way. Fixed by: `fix_makefile_literal_newline_escape` (converts `\n\n` → blank line, `\n` → recipe continuation), extended `fix_makefile_literal_tab_escape` for `\@`, and `fix_makefile_escaped_dollar` for `\$(cmd)` → `cmd`.

39. **C# `using` after top-level statements (CS1529)**
   - Models sometimes write `using Microsoft.EntityFrameworkCore;` after `var builder = ...` top-level statements. Fixed: `fix_csharp_using_order` reflex moves all `using` directives to the file top.

40. **C# verbatim string with backslash escaping (CS1056)**
   - Model writes `@"{\"id\":1,...}"` (verbatim string with `\"` inside). In C# verbatim strings, `\"` is not an escape — the `"` terminates the string. Fixed: `fix_csharp_verbatim_string_escape` converts `@"...\"..."` to regular strings by removing the `@` prefix.

41. **C# keyword prefix artifacts (CS1513)**
   - Model occasionally emits `tnamespace` (stray `t` fused to `namespace`) or similar single-character prefixes to C# keywords, causing cascading parse errors. Fixed: `fix_csharp_keyword_prefix_artifacts` detects 1-2 lowercase letters or a symbol directly prefixed to a keyword at line start and strips the prefix.

42. **xUnit test project missing .csproj (dotnet test failure)**
   - `dotnet test ./Tests` fails with "no project file found" when the test folder has `.cs` files but no `Tests.csproj`. Model generates test code but not the project file. Fixed: `ground_plan` now auto-creates `Tests/Tests.csproj` with xUnit + WebApplicationFactory package references when `Tests/*.cs` files exist.

43. **EF Core packages absent from auto-generated .csproj**
   - The grounding-generated `.csproj` uses the minimal SDK template without package references. Files using `DbContext`, `UseSqlite`, etc. then fail with CS0234. Fixed: `_csproj_content(include_ef_core=True)` is used when the plan text mentions EntityFramework/DbContext/WebApplicationFactory, adding EF Core + SQLite + ASP.NET packages.

## Resolved

- **Missing `fix_sqlite_in_memory` function** — obsolete. AST fixer pass and the orphaned sqlite sensor removed in commit `07717cc`.
- **SQLite persistence across test runs** — addressed via writer‑side test isolation (commit `4dc186c`) instead of a post‑hoc sensor.
- **Git commit command failing on BSD grep** — `sit.sh` no longer uses `grep -Po`; switched to `awk`.
- **Version extraction brittleness** — `sit.sh:102` uses `awk -F'"' '/__version__/ {print $2}' src/mu/__init__.py`.
- **Duplicate dojo cleaning logic** — `sit.sh` now has a single cleanup block guarded by `SKIP_CLEAN`.
- **p8 (Node todo) "No tests found"** — model uses `_test.js` naming; fixed by `fix_jest_no_tests_found` reflex + node-env skill guidance.
- **p9 (Vue todo) TypeScript lint before npm install** — tsc ran before deps installed; fixed by skipping tsc when node_modules absent + `fix_vitest_globals` reflex.
- **Makefile recipe instead of prerequisites** — model writes `all:\n\tinstall test` (recipe, shell command) instead of `all: install test` (prerequisites). Fixed by `fix_makefile_recipe_is_prerequisite_list` reflex; applies to any Makefile where recipe lines consist solely of declared target names.
- **Python venv never created when Makefile broken** — repair loop never created `.venv` when the Makefile failed before the venv setup step. Fixed by `reapply()` creating `.venv` from `requirements.txt` when `.venv/bin/pip` is absent. Mirrors the existing npm-install pattern for Node.
- **Jest/Vitest config reverted by repair model** — repair model would rewrite `package.json`/`vite.config.ts`, removing `testRegex`/`globals:true` added in the pre-flight pass. Fixed by calling `fix_jest_no_tests_found` + `fix_vitest_globals` inside `reapply()` on every repair iteration.
- **Literal `\n` in JS/TS source** — model occasionally writes the last line(s) of a JS file with literal `\n` instead of real newlines, causing "Expecting Unicode escape sequence \uXXXX". `fix_literal_newlines` extended with a JS/TS mode that fires for any literal `\n` outside a string literal.
- **Missing Node.js built-in requires** — model uses `path.join`, `os.tmpdir`, `fs.readFileSync` etc. without importing them. Added `fix_js_missing_requires` reflex (mirrors Python/Go equivalents); driven by usage patterns, not problem-specific.
- **Module-level env-var constant breaks test isolation** — `const DATA_FILE = process.env.TODO_FILE || 'data.json'` is captured once at module load; `beforeEach` changes have no effect. Added `fix_js_env_data_file` reflex that converts module-level env-var constants to getter functions.
- **`fix_makefile_missing_compile_rule` adds bogus C rules for non-C projects** — when `all: build test` is missing targets and no `.c` files exist, the reflex would add `cc -o build main.c` (nonsensical for Python/Node). Fixed: reflex now returns False when no `.c` sources are present.
- **SQLAlchemy URL not converted to in-memory** — `fix_sqlite_test_isolation` replaced `todos.db` with `:memory:` but left SQLAlchemy URLs like `sqlite:///todos.db` unchanged. Fixed: reflex now replaces SQLAlchemy URLs with `sqlite:///:memory:` first.
- **python-writer skill allowed plain SQLAlchemy** — skill said "no Flask-SQLAlchemy" but didn't mention plain SQLAlchemy. Model used `SQLAlchemy` ORM. Updated skill to explicitly forbid any ORM: "Use sqlite3 directly — no SQLAlchemy, no ORM."
- **Malformed `- - [ ]` plan task lines** — planner occasionally emits `- - [ ] file.py` (extra leading dash) instead of `- [ ] file.py`. Parser only matched the first correct line, silently skipping all malformed tasks. Unfound files caused 14-LLM-call repair blowups (42K tokens wasted per session). Fixed: `parse_content` normalizes lines matching `^[\s-]+(\[[ x~]\]\s+\S+.*)` to `- [...]` before the regex match (commit `c506949`).
- **`fix_orphan_top_level_commands` missed tab-indented orphans** — the Makefile reflex that wraps bare commands into an `all:` target had a bug: tab-indented commands before the first target were put into `clean` (preserved as-is) instead of `orphans` (wrapped). `make` still reported "commands commence before first target" after repair. Fixed: added `seen_target` tracking; tab lines before any target now go to `orphans` (commit `c506949`).
- **SQLite per-method `:memory:` connections cause `no such table`** — after `fix_sqlite_test_isolation` converts file paths to `:memory:`, a class that opens `sqlite3.connect(self.db_path)` in each method gets a separate empty database per call. Table created in `__init__`/`_create_table` doesn't exist in the connection opened by `add()`/`list()`. Fixed: `fix_sqlite_memory_multi_connect` reflex consolidates all per-method connects into one `self._conn`, removes `conn.close()` calls that would close it; repair-python skill hint added (commit `c506949`).
- **Unquoted `--filter` argument causes bash syntax error in test commands** — planner sometimes writes `dotnet test --filter FullyQualifiedName~*.Method()` where `()` is interpreted by bash as a subshell, causing `syntax error near unexpected token '('`. Fixed: `normalize_test_command` in `plan.py` now wraps unquoted `--filter` values containing `()~*` in double quotes (commit `6d86d4e`).
- **Planner uses `pytest` as Test Command for Rust projects** — planner omits `## Test Command` section for Rust programs; fallback defaulted to `pytest tests/fib_test.rs` which fails immediately. Fixed: (a) task-planner skill adds explicit Rust rule requiring `cargo test`; (b) `normalize_test_command` converts `pytest *.rs` → `cargo test`; (c) `_final_test_gate` fallback now selects cargo/go/dotnet runners by file extension (commit `3c89129`).

*This file is intended to be updated continuously as new challenges arise.*
