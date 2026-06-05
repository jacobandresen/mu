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

44. **Syntax error in HTML template**
  - Ensure proper HTML syntax and correct use of tags in Vue components to avoid runtime errors.

45. **Mock data file not defined**
  - Ensure mock variables are properly declared and initialized before use in test cases.

46. **Missing using directives**
  - Ensure all necessary namespaces are imported in C# files to avoid type not found errors.

47. **Unterminated string literal**

One common pitfall is leaving triple‑quoted strings open (missing the closing `"""`), which causes syntax errors later in the file when Python expects a matching delimiter. Always ensure every multi‑line string literal you start with ``"""`` ends with the same sequence, and check for stray backslashes or missing quotes near long comment blocks.

48. **Unknown option in Jest command**
  - Watch for using unrecognized options with Jest; ensure commands are correctly spelled and supported.

49. **Incorrect text assertion in test**
  - Tests often assert on the wrong text content; ensure assertions match expected output accurately.

50. **Syntax error in JavaScript code**
  - Syntax errors in the source code can cause tests to fail. Ensure proper syntax and correct use of language features.


*This file is intended to be updated continuously as new challenges arise.*

51. **Incorrect HTML template syntax**
  - Ensure proper HTML tags and attributes are used in Vue components to avoid parsing errors during build processes.

52. **Mocking conflicts**
  - Conflicting imports between mocks and actual modules can cause build errors; ensure mocks are used lazily or with unique names to avoid clashes.

