# Challenges

Recurring failures observed in dojo runs. Updated as new patterns emerge and existing ones are resolved by reflexes or skills.

## Open

### Group 1 — Degenerate / malformed generation

1. **Generic syntax errors** — Python indentation/colons, C#/Rust unmatched braces, Go composite-literal missing commas, JS syntax, missing semicolons. Most residual cases are model quality. Python def/class bodies written at the parent's column (`expected an indented block`) covered by `fix_python_unindented_body`.
2. **Unterminated string literals** — Python triple-quoted strings left open, Go strings missing closing quote. Covered by reflexes; still model-frequent.
3. **Spurious / unused imports** — `import __name__`/`import self` in Python; unused Rust `use` causing build failures. Cleaned by reflexes.
4. **C# generation artifacts** — top-level statements before namespace (CS1529); verbatim string `\"` escaping (CS1056); stray keyword prefixes like `tnamespace` (CS1513); lambda chains closed with `{){` instead of `)` (CS1026, `fix_csharp_lambda_brace_confusion`). Each covered by a named reflex.
5. **Makefile escape artifacts** — recipe lines need a literal TAB; lean-retry emits literal `\n`, `\t`, `\@`. Covered by the makefile reflex family.
6. **Degenerate repetition** — `print(f"{task[print(f"{task[…`; fought at the sampler (`MU_REPEAT_PENALTY`) and by the degeneration guard (`MU_DEGEN_GUARD`). Not reflex-recoverable. Top residual failure.
7. **C forward declarations / nested definitions** — `call to undeclared function`; `function definition is not allowed here`. Distillation names both; no scan reflex yet.

### Group 2 — Full-stack orchestration / multi-file

8. **C# / ASP.NET scaffolding** — `dotnet test` needs a Tests.csproj (auto-created by `ground_plan`); EF Core/SQLite/ASP.NET package refs absent from minimal SDK template; occasional malformed `.csproj` XML (MSB4067); package majors above the TFM (NU1202, `fix_csharp_package_tfm_mismatch`); the test SDK's auto-generated `Main` clashing with the user's (CS0017, `fix_csharp_test_program_conflict`); duplicate types across files in the multi-project layout (CS0101 — `run_staged` orphan-`.cs` cleanup); `dotnet test` from a dir with no csproj (MSB1003, `fix_dotnet_test_cwd`). **p10 remains 0-pass** — cascading CS errors (run 7: CS0101 ×14, MSB1003 ×8, CS0053 ×8), repair oscillates.
9. **Vue / Vitest / Jest setup** — Jest `_test.js` naming → "No tests found"; missing `globals:true`; vitest watch-mode hang; missing `vue` peer dep; `tsc --noEmit` before `npm install`; tests run under plain `node` so jest globals are undefined (`describe/test is not a function` — the test command must be `npx jest`, diagnose hints at it). Each covered by a named reflex or hint.
10. **Build-target inconsistency & misplaced files** — plans name entry-point targets the build file never defines; lean-retry writes files to wrong subdirs. Mitigated by relocation + stale-file cleanup.
11. **Repair-context budget** — the loaded window bounds prompt + generation together; large skill stacks and accumulated repair history overflow it (HTTP 400). Mitigated by lean repair system, `_strip_ansi`, the repair-loop unit budget (`_fit_prompt_budget`), a 1536-token generation reserve, and chat()-level prompt shrinking (`_shrink_oversized`).

### Group 3 — Model ceiling

12. **Test isolation design** — model omits `beforeEach/afterEach`; shared state leaks across tests. `fix_js_env_data_file` enables isolation when the model writes the hooks; ~50% pass.
13. **Stateful-backend lifecycle rewrites** — Flask per-operation `sqlite3.connect` vs `:memory:` destroys data each call. Needs architectural rewrite beyond the 7B repair loop.
14. **Missing imports** — Python omits the import of the module under test (`NameError`); `ModuleNotFoundError` on `app`/`main`; missing C# `using`. Partly patched; still frequent.
15. **Incorrect test assertions** — wrong values, undeclared mock data, `KeyError` on JSON response, endpoint not defined, bad CLI args. Test-design quality; not reflex-recoverable.

### Group 4 — Harness / environment

16. **Environment hygiene** — system-wide vs Homebrew Python (use venvs); server port already in use; empty session log → no distillable cause.

17. **Syntax errors in test files** — JS: same-scope `const` re-declaration (10+ sessions; was mislabeled "Jest ESM" because the Jest banner shadowed the Babel SyntaxError detail — diagnose now demotes banner-level hints) and `.[0]` member access; both covered by `fix_js_same_scope_redeclaration` and `fix_js_dot_bracket_access`. C#: unmatched parentheses/semicolons in test files — generic, see item 1; stuttered duplicate method-signature openers covered by `fix_csharp_consecutive_duplicate_signatures`.

