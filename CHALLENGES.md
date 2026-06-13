# Challenges

Recurring failures observed in dojo runs. Updated as new patterns emerge and existing ones are resolved by reflexes or skills.

Each item links to its detailed page in `docs/challenges/` — which problems exhibit it and the relevant reflexes. For a grouped, status-at-a-glance overview see [docs/challenges/README.md](docs/challenges/README.md). Per-problem pages live in [`docs/problems/`](docs/problems/). For external tools that could address these classes (and reflexes-vs-tools trade-offs), see [TOOLS.md](TOOLS.md).

## Open

### Group 1 — Degenerate / malformed generation

1. **[Generic syntax errors](docs/challenges/generic-syntax-errors.md)** — Python indentation/colons, C#/Rust unmatched braces, Go composite-literal missing commas, JS syntax, missing semicolons. Unindented def/class bodies covered by `fix_python_unindented_body`; most other residual cases are model quality.
2. **[Unterminated string literals](docs/challenges/unterminated-string-literals.md)** — Python triple-quoted strings left open, Go strings missing closing quote. Covered by reflexes; still model-frequent.
3. **[Spurious / unused imports](docs/challenges/spurious-unused-imports.md)** — `import __name__`/`import self` in Python; unused Rust `use` causing build failures. Cleaned by reflexes.
4. **[C# generation artifacts](docs/challenges/csharp-generation-artifacts.md)** — top-level statements before namespace (CS1529); verbatim string `\"` escaping (CS1056); stray keyword prefixes like `tnamespace` (CS1513); lambda chains closed with `{){` (CS1026); stuttered duplicate signature openers. Each covered by a named reflex.
5. **[Makefile escape artifacts](docs/challenges/makefile-escape-artifacts.md)** — recipe lines need a literal TAB; lean-retry emits literal `\n`, `\t`, `\@`. Covered by the makefile reflex family.
6. **[Degenerate repetition](docs/challenges/degenerate-repetition.md)** — `print(f"{task[print(f"{task[…`; fought at the sampler (`MU_REPEAT_PENALTY`) and by the degeneration guard (`MU_DEGEN_GUARD`). Not reflex-recoverable. Top residual failure.
7. **[C forward declarations / nested definitions](docs/challenges/c-forward-declarations.md)** — `call to undeclared function`; `function definition is not allowed here`. Distillation names both; no scan reflex yet.

### Group 2 — Full-stack orchestration / multi-file

8. **[C# / ASP.NET scaffolding](docs/challenges/csharp-aspnet-scaffolding.md)** — test csproj, EF Core/SQLite/ASP.NET package refs, NU1202 TFM mismatch, CS0017 duplicate entry point, CS0101 duplicate types, MSB1003 missing project. **p10 remains 0-pass** (run 7: CS0101 ×14, MSB1003 ×8, CS0053 ×8) — cascading CS errors, repair oscillates.
9. **[Vue / Vitest / Jest setup](docs/challenges/vue-vitest-jest-setup.md)** — Jest `_test.js` naming → "No tests found"; missing `globals:true`; vitest watch-mode hang; missing `vue` peer dep; jest globals undefined when run via plain `node` instead of `npx jest`. Each covered by a named reflex or hint.
10. **[Build-target inconsistency & misplaced files](docs/challenges/build-target-inconsistency.md)** — plans name entry-point targets the build file never defines; lean-retry writes files to wrong subdirs. Mitigated by relocation + stale-file cleanup.
11. **[Repair-context budget](docs/challenges/repair-context-budget.md)** — the loaded window bounds prompt + generation together; large skill stacks and accumulated repair history overflow it (HTTP 400). Mitigated by lean repair system, `_strip_ansi`, `_fit_prompt_budget`, a 1536-token generation reserve, and chat()-level prompt shrinking (`_shrink_oversized`).

### Group 3 — Model ceiling

12. **[Test isolation design](docs/challenges/test-isolation-design.md)** — model omits `beforeEach/afterEach`; shared state leaks across tests. `fix_js_env_data_file` enables isolation when the model writes the hooks; ~50% pass.
13. **[Stateful-backend lifecycle rewrites](docs/challenges/stateful-backend-lifecycle.md)** — Flask per-operation `sqlite3.connect` vs `:memory:` destroys data each call. Needs architectural rewrite beyond the 7B repair loop.
14. **[Missing imports](docs/challenges/missing-imports.md)** — Python omits the import of the module under test (`NameError`); `ModuleNotFoundError` on `app`/`main`; missing C# `using`. Partly patched; still frequent.
15. **[Incorrect test assertions](docs/challenges/incorrect-test-assertions.md)** — wrong values, undeclared mock data, `KeyError` on JSON response, endpoint not defined, bad CLI args. Test-design quality; not reflex-recoverable.

### Group 4 — Harness / environment

16. **[Environment hygiene](docs/challenges/environment-hygiene.md)** — system-wide vs Homebrew Python (use venvs); server port already in use; empty session log → no distillable cause.
17. **[Syntax errors in test files](docs/challenges/test-file-syntax-errors.md)** — JS same-scope `const` re-declaration (was mislabeled "Jest ESM") and `.[0]` member access (`fix_js_same_scope_redeclaration`, `fix_js_dot_bracket_access`); C# stuttered method-signature openers (`fix_csharp_consecutive_duplicate_signatures`).
