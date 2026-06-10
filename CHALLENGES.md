# Challenges Observed in the Mu System

Tracks the most frequent or significant challenges encountered while running the Mu dojo problems and developing the Mu codebase. Updated as new challenges are identified and old ones are resolved.

Consolidated 2026-06-07: 68 sprawling entries → deduplicated and **grouped under the three
README "Top 3 challenges"** (degenerate generation; full-stack orchestration; separating
model-ceiling from deterministic), plus a harness/tooling group. Near-duplicate entries were
merged; substantive per-reflex documentation was preserved.

## Open

### Group 1 — Degenerate / malformed generation (README Top-3 #1)
*The weak model emits structurally broken output. Deterministic variants are caught by
language reflexes; the rest is model quality and must not be overfit.*

1. **Generic syntax errors in generated source** — recurring per language: Python
   indentation/colons, C#/Rust unmatched braces & stray closing delimiters, Go composite-literal
   missing commas / unexpected newlines, JS syntax, SQL line-continuation, missing semicolons.
   *(merged: old #10,13,14,15,16,18,19,20,21,50,53,54,55)*. Distillation now names Go `syntax
   error:` and MSBuild `MSBxxxx` causes (`diagnose.py`, 2026-06-07); most residual cases are
   model quality.
2. **Unterminated string literals** — Python triple-quoted (`"""…`) left open, or Go strings
   missing a closing quote. Covered by `fix_*` + distillation; still model-frequent. *(merged #23,47)*
3. **Spurious / unused imports** — nonsensical `import __name__`/`import self` (Python) or
   unused Rust imports causing build failures. Cleanup via `py_autofix`/reflexes. *(merged #2,22)*
4. **C# generation artifacts (documented reflexes)** — top-level statements before namespace
   (CS1529, `fix_csharp_using_order`); verbatim string `\"` escaping (CS1056,
   `fix_csharp_verbatim_string_escape`); stray keyword prefixes like `tnamespace` (CS1513,
   `fix_csharp_keyword_prefix_artifacts`); top-level-before-type ordering. *(merged #17,39,40,41)*
5. **Makefile structure / escape artifacts** — recipe lines must start with a literal TAB
   (spaces → "missing separator"); lean-retry also emits literal `\n`, `\t`, `\@`, `\$(cmd)`.
   Covered by the makefile reflex family (`fix_makefile_space_indent`,
   `fix_makefile_literal_newline_escape`, `fix_makefile_literal_tab_escape`,
   `fix_makefile_escaped_dollar`). *(merged #5,38)*
6. **Degenerate repetition / corrupt-from-first-token output** — the dominant README #1 case
   (e.g. `print(f"{task[print(f"{task[…`); fought at the sampler (`MU_REPEAT_PENALTY`) and by
   the degeneration guard (`MU_DEGEN_GUARD`). Not reflex-recoverable. Still the top residual.

### Group 2 — Full-stack orchestration / multi-file (README Top-3 #2, esp. p10)
*Coordinating backend + frontend + cross-language test harness exceeds a small model's
planning coherence in the context budget.*

7. **C# / ASP.NET project scaffolding** — `dotnet test` needs a `Tests.csproj` the model omits
   (auto-created by `ground_plan`); EF Core/SQLite/ASP.NET package refs absent from the minimal
   SDK template (`_csproj_content(include_ef_core=True)`); p10 remains model-limited (cascading
   CS errors, repair oscillates). *(merged #30,42,43)*
8. **Vue / Vitest / Jest setup** — Jest `_test.js` naming → "No tests found"
   (`fix_jest_no_tests_found`); missing `globals:true` (`fix_vitest_globals`); `"test":"vitest"`
   hangs in watch mode (`fix_vitest_watch_mode`); missing `vue` peer dep (`fix_vue_missing_package`);
   `tsc --noEmit` linted before `npm install`. *(merged #26,27,28,36,37,52)*
9. **Build-target inconsistency & misplaced files** — plans name entry-point targets the build
   file never defines; lean-retry writes files to wrong subdirs (`src/vite.config.ts`,
   `backend/Program.cs`). Mitigated by relocation + stale-file cleanup. *(merged #7,35)*
10. **Repair-context budget** — large combined skill stacks overflow the 6000-token context
    (400 errors); Vitest ANSI codes inflate test output ~10×; writer 400 on >3 skills. Mitigated
    by lean repair system, skill trimming, `_strip_ansi`. *(merged #25,31,34)*

### Group 3 — Model-ceiling vs deterministic (README Top-3 #3)
*Recurring same-root-cause failures are reflex candidates; run-to-run variation is model
quality and must not be overfit.*

11. **Test isolation design (model-ceiling)** — model omits `beforeEach/afterEach`; shared
    JSON/SQLite state leaks across tests. `fix_js_env_data_file` enables isolation *when* the
    model writes the hooks; ~50% pass. *(merged #8,32,62)*
12. **Stateful-backend lifecycle rewrites (model-ceiling)** — Flask per-operation `sqlite3.connect`
    vs `:memory:` destroys data each call; Flask test calls ORM methods then asserts HTTP
    `status_code`. Both need an architectural rewrite beyond the 7B repair loop. *(merged #29,33)*
13. **Model forgets required imports** — Python omits the import of the module under test
    (`NameError`; `fix_test_import_module`), `ModuleNotFoundError` on `app`/`main`, relative
    imports run as a module, missing C# `using`. Partly patched; still frequent. *(merged #1,9,11,46,67,68)*
14. **Incorrect test assertions / mock wiring** — assertions on wrong text/values, undeclared
    mock data, `KeyError` on JSON response, endpoint not defined, CLI called with bad args,
    missing positional format arg, export defined after `module.exports`. Largely test-design
    quality. *(merged #6,45,49,56,58,59,63,64)*
15. **Discipline: no overfitting; repair-loop exhaustion** — sensors/reflexes must stay generic
    (honesty prime directive); the repair loop can still exhaust without a fix despite plan-file
    context + syntax-rollback. *(merged #3,4)*

### Group 4 — Harness / environment (not model quality)
16. **Environment & runtime hygiene** — system-wide installs vs Homebrew Python (use venvs);
    server port already in use; empty session log → no distillable cause. *(merged #12,61,65)*

---
*Updated continuously as challenges arise and reflexes/skills resolve them. Items tagged
"(merged #N)" trace back to the pre-2026-06-07 flat numbering.*

17. **SKIP**

18. **Incorrect import statements**
  - Ensure that all imported names exist and are spelled correctly in the module being imported from.

19. **Incorrect mock expectations**
  - Mock functions may not match the actual arguments passed during calls; ensure mocks accurately reflect the expected inputs and outputs.

20. **Duplicate attribute in HTML**
  - Ensure that each HTML element has unique attributes to avoid syntax errors during rendering.

21. **External environment management**
  - Be aware that some environments may not allow installing packages system-wide and require using virtual environments instead. Always use a virtual environment to manage Python dependencies.

22. **HTML attribute syntax error**
  - Attribute names in HTML cannot contain double quotes (`"`) and single quotes (`'`). Use single quotes for attributes if the value contains double quotes.

23. **Mock expectations not met**
  - Mock functions in Jest are not being called as expected during test execution; ensure mock implementations are correctly set up and invoked within the test cases.

24. **Syntax errors in test code**
  - Syntax errors in the xUnit test file can cause build failures and prevent further progress. Ensure all braces, semicolons, and other syntax elements are correctly placed.

