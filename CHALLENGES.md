# Challenges

Recurring failures observed in dojo runs. Updated as new patterns emerge and existing ones are resolved by reflexes or skills.

## Open

### Group 1 — Degenerate / malformed generation

1. **Generic syntax errors** — Python indentation/colons, C#/Rust unmatched braces, Go composite-literal missing commas, JS syntax, missing semicolons. Most residual cases are model quality.
2. **Unterminated string literals** — Python triple-quoted strings left open, Go strings missing closing quote. Covered by reflexes; still model-frequent.
3. **Spurious / unused imports** — `import __name__`/`import self` in Python; unused Rust `use` causing build failures. Cleaned by reflexes.
4. **C# generation artifacts** — top-level statements before namespace (CS1529); verbatim string `\"` escaping (CS1056); stray keyword prefixes like `tnamespace` (CS1513); lambda chains closed with `{){` instead of `)` (CS1026, `fix_csharp_lambda_brace_confusion`). Each covered by a named reflex.
5. **Makefile escape artifacts** — recipe lines need a literal TAB; lean-retry emits literal `\n`, `\t`, `\@`. Covered by the makefile reflex family.
6. **Degenerate repetition** — `print(f"{task[print(f"{task[…`; fought at the sampler (`MU_REPEAT_PENALTY`) and by the degeneration guard (`MU_DEGEN_GUARD`). Not reflex-recoverable. Top residual failure.
7. **C forward declarations / nested definitions** — `call to undeclared function`; `function definition is not allowed here`. Distillation names both; no scan reflex yet.

### Group 2 — Full-stack orchestration / multi-file

8. **C# / ASP.NET scaffolding** — `dotnet test` needs a Tests.csproj (auto-created by `ground_plan`); EF Core/SQLite/ASP.NET package refs absent from minimal SDK template. p10 remains model-limited (cascading CS errors, repair oscillates).
9. **Vue / Vitest / Jest setup** — Jest `_test.js` naming → "No tests found"; missing `globals:true`; vitest watch-mode hang; missing `vue` peer dep; `tsc --noEmit` before `npm install`. Each covered by a named reflex.
10. **Build-target inconsistency & misplaced files** — plans name entry-point targets the build file never defines; lean-retry writes files to wrong subdirs. Mitigated by relocation + stale-file cleanup.
11. **Repair-context budget** — large skill stacks overflow the 6000-token context; Vitest ANSI codes inflate test output ~10×. Mitigated by lean repair system, skill trimming, `_strip_ansi`.

### Group 3 — Model ceiling

12. **Test isolation design** — model omits `beforeEach/afterEach`; shared state leaks across tests. `fix_js_env_data_file` enables isolation when the model writes the hooks; ~50% pass.
13. **Stateful-backend lifecycle rewrites** — Flask per-operation `sqlite3.connect` vs `:memory:` destroys data each call. Needs architectural rewrite beyond the 7B repair loop.
14. **Missing imports** — Python omits the import of the module under test (`NameError`); `ModuleNotFoundError` on `app`/`main`; missing C# `using`. Partly patched; still frequent.
15. **Incorrect test assertions** — wrong values, undeclared mock data, `KeyError` on JSON response, endpoint not defined, bad CLI args. Test-design quality; not reflex-recoverable.

### Group 4 — Harness / environment

16. **Environment hygiene** — system-wide vs Homebrew Python (use venvs); server port already in use; empty session log → no distillable cause.

17. **Syntax errors in test files** — JS: same-scope `const` re-declaration (10+ sessions; was mislabeled "Jest ESM" because the Jest banner shadowed the Babel SyntaxError detail — diagnose now demotes banner-level hints) and `.[0]` member access; both covered by `fix_js_same_scope_redeclaration` and `fix_js_dot_bracket_access`. C#: unmatched parentheses/semicolons in test files — generic, see item 1.

18. **SKIP**

19. **Redundant import statements**
  - Redefinition of imports can lead to confusion and errors; ensure each import is used only once per file.

20. **Stalled compilation**
  - The developer may be waiting for an IDE to auto-complete code or a build system to detect changes before proceeding. Ensure that all necessary files are saved and the build system is properly configured to recognize changes.

21. **XML syntax in project file**
  - Project files should use XML syntax correctly; ensure all tags are properly closed and nested.

22. **Test state leaks across runs**
  - Tests sharing mutable storage accumulate state between invocations; require setup/teardown that isolates state per test.

23. **Missing dependencies**
  - Ensure all required packages are installed before running tests. Use `npm install` to add missing modules like 'vitest'.

