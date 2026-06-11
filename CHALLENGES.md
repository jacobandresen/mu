# Challenges Observed in the Mu System

Tracks the most frequent or significant challenges encountered while running the Mu dojo problems and developing the Mu codebase. Updated as new challenges are identified and old ones are resolved.

Consolidated 2026-06-07: 68 sprawling entries → deduplicated and grouped under three themes (degenerate generation; full-stack orchestration; separating model-ceiling from deterministic), plus a harness/tooling group. Near-duplicate entries were merged; substantive per-reflex documentation was preserved.

Trimmed 2026-06-11: removed entries already covered by existing reflexes/diagnose rules and duplicates of grouped items.

## Open

### Group 1 — Degenerate / malformed generation
*The weak model emits structurally broken output. Deterministic variants are caught by
language reflexes; the rest is model quality and must not be overfit.*

1. **Generic syntax errors in generated source** — recurring per language: Python
   indentation/colons, C#/Rust unmatched braces & stray closing delimiters, Go composite-literal
   missing commas / unexpected newlines, JS syntax, SQL line-continuation, missing semicolons.
   Distillation now names Go `syntax error:` and MSBuild `MSBxxxx` causes (`diagnose.py`); most
   residual cases are model quality.
2. **Unterminated string literals** — Python triple-quoted (`"""…`) left open, or Go strings
   missing a closing quote. Covered by `fix_*` + distillation; still model-frequent.
3. **Spurious / unused imports** — nonsensical `import __name__`/`import self` (Python) or
   unused Rust imports causing build failures. Cleanup via `py_autofix`/reflexes.
4. **C# generation artifacts (documented reflexes)** — top-level statements before namespace
   (CS1529, `fix_csharp_using_order`); verbatim string `\"` escaping (CS1056,
   `fix_csharp_verbatim_string_escape`); stray keyword prefixes like `tnamespace` (CS1513,
   `fix_csharp_keyword_prefix_artifacts`); top-level-before-type ordering.
5. **Makefile structure / escape artifacts** — recipe lines must start with a literal TAB
   (spaces → "missing separator"); lean-retry also emits literal `\n`, `\t`, `\@`, `\$(cmd)`.
   Covered by the makefile reflex family.
6. **Degenerate repetition / corrupt-from-first-token output** — (e.g. `print(f"{task[print(f"{task[…`);
   fought at the sampler (`MU_REPEAT_PENALTY`) and by the degeneration guard (`MU_DEGEN_GUARD`).
   Not reflex-recoverable. Still the top residual.
7. **C forward declarations / nested definitions** — `call to undeclared function` when the
   model puts a definition below its call site; nested function bodies (`function definition is
   not allowed here`). Distillation names both; no scan reflex yet.

### Group 2 — Full-stack orchestration / multi-file
*Coordinating backend + frontend + cross-language test harness exceeds a small model's
planning coherence in the context budget.*

8. **C# / ASP.NET project scaffolding** — `dotnet test` needs a `Tests.csproj` the model omits
   (auto-created by `ground_plan`); EF Core/SQLite/ASP.NET package refs absent from the minimal
   SDK template (`_csproj_content(include_ef_core=True)`); p10 remains model-limited (cascading
   CS errors, repair oscillates).
9. **Vue / Vitest / Jest setup** — Jest `_test.js` naming → "No tests found"
   (`fix_jest_no_tests_found`); missing `globals:true` (`fix_vitest_globals`); `"test":"vitest"`
   hangs in watch mode (`fix_vitest_watch_mode`); missing `vue` peer dep (`fix_vue_missing_package`);
   `tsc --noEmit` linted before `npm install`.
10. **Build-target inconsistency & misplaced files** — plans name entry-point targets the build
    file never defines; lean-retry writes files to wrong subdirs (`src/vite.config.ts`,
    `backend/Program.cs`). Mitigated by relocation + stale-file cleanup.
11. **Repair-context budget** — large combined skill stacks overflow the 6000-token context
    (400 errors); Vitest ANSI codes inflate test output ~10×; writer 400 on >3 skills. Mitigated
    by lean repair system, skill trimming, `_strip_ansi`.

### Group 3 — Model-ceiling vs deterministic
*Recurring same-root-cause failures are reflex candidates; run-to-run variation is model
quality and must not be overfit.*

12. **Test isolation design (model-ceiling)** — model omits `beforeEach/afterEach`; shared
    JSON/SQLite state leaks across tests. `fix_js_env_data_file` enables isolation *when* the
    model writes the hooks; ~50% pass.
13. **Stateful-backend lifecycle rewrites (model-ceiling)** — Flask per-operation `sqlite3.connect`
    vs `:memory:` destroys data each call; Flask test calls ORM methods then asserts HTTP
    `status_code`. Both need an architectural rewrite beyond the 7B repair loop.
14. **Model forgets required imports** — Python omits the import of the module under test
    (`NameError`; `fix_test_import_module`), `ModuleNotFoundError` on `app`/`main`, relative
    imports run as a module, missing C# `using`. Partly patched; still frequent.
15. **Incorrect test assertions / mock wiring** — assertions on wrong text/values, undeclared
    mock data, `KeyError` on JSON response, endpoint not defined, CLI called with bad args,
    missing positional format arg, export defined after `module.exports`. Largely test-design
    quality.
16. **Discipline: no overfitting; repair-loop exhaustion** — sensors/reflexes must stay generic
    (honesty prime directive); the repair loop can still exhaust without a fix despite plan-file
    context + syntax-rollback.

### Group 4 — Harness / environment
17. **Environment & runtime hygiene** — system-wide installs vs Homebrew Python (use venvs);
    server port already in use; empty session log → no distillable cause.

---
*Updated continuously as challenges arise and reflexes/skills resolve them.*

18. **Missing closing brace**
  - Ensure every opening curly brace `{` has a corresponding closing brace `}` in the same scope.

