# Challenges — overview

One page per recurring failure class mu meets in the dojo. Each lists the problems that exhibit it and the reflexes/mechanisms that address it. **Status** is how well the harness handles it today.

_Status legend: **covered** = a reflex resolves it deterministically · **partial** = handled for common shapes, residue remains · **mitigated** = bounded by a mechanism, not eliminated · **model-ceiling** = beyond the weak model, no reflex can reach · **open** = no fixer yet._

## Group 1 — Degenerate / malformed generation

| Challenge | Status | Problems |
|---|---|---|
| [Generic syntax errors](generic-syntax-errors.md) | partial | p4, p5, p2 |
| [Unterminated string literals](unterminated-string-literals.md) | covered | p2 |
| [Spurious / unused imports](spurious-unused-imports.md) | covered | p6, p2 |
| [C# generation artifacts](csharp-generation-artifacts.md) | covered | p4, p10 |
| [Makefile escape artifacts](makefile-escape-artifacts.md) | covered | p1, p3, p7 |
| [Degenerate repetition](degenerate-repetition.md) | model-ceiling | p8, p10 |
| [C forward declarations / nested definitions](c-forward-declarations.md) | open | p1, p3 |

## Group 2 — Full-stack orchestration / multi-file

| Challenge | Status | Problems |
|---|---|---|
| [C# / ASP.NET scaffolding](csharp-aspnet-scaffolding.md) | partial — **p10 0-pass** | p4, p10 |
| [Vue / Vitest / Jest setup](vue-vitest-jest-setup.md) | covered | p8, p9, p10 |
| [Build-target inconsistency & misplaced files](build-target-inconsistency.md) | mitigated | p1, p5, p10 |
| [Repair-context budget](repair-context-budget.md) | mitigated | p8, p9, p10 |

## Group 3 — Model ceiling

| Challenge | Status | Problems |
|---|---|---|
| [Test isolation design](test-isolation-design.md) | partial (~50%) | p2, p7, p8 |
| [Stateful-backend lifecycle rewrites](stateful-backend-lifecycle.md) | model-ceiling | p7, p2 |
| [Missing imports](missing-imports.md) | partial | p7, p2, p10 |
| [Incorrect test assertions](incorrect-test-assertions.md) | model-ceiling | p9, p8 |

## Group 4 — Harness / environment

| Challenge | Status | Problems |
|---|---|---|
| [Environment hygiene](environment-hygiene.md) | covered | p2, p7 |
| [Syntax errors in test files](test-file-syntax-errors.md) | covered | p8, p4 |

## Open`
entries and the planner injects the relevant ones into the next goal's prompt.

This is the *data* the learning loop reads and writes. For the human-readable, grouped
overview — status per class, problems affected, relevant reflexes — see
[README.md](README.md); per-problem pages are in [`../problems/`](../problems/) and
external-tool options in [TOOLS.md](../../TOOLS.md).

## Open

### Group 1 — Degenerate / malformed generation

1. **[Generic syntax errors](generic-syntax-errors.md)** — Python indentation/colons, C#/Rust unmatched braces, Go composite-literal missing commas, JS syntax, missing semicolons. Unindented def/class bodies covered by [`fix_python_unindented_body`](../../src/mu/reflexes/python/fix_python_unindented_body.py); most other residual cases are model quality.
2. **[Unterminated string literals](unterminated-string-literals.md)** — Python triple-quoted strings left open, Go strings missing closing quote. Covered by reflexes; still model-frequent.
3. **[Spurious / unused imports](spurious-unused-imports.md)** — `import __name__`/`import self` in Python; unused Rust `use` causing build failures. Cleaned by reflexes.
4. **[C# generation artifacts](csharp-generation-artifacts.md)** — top-level statements before namespace (CS1529); verbatim string `\"` escaping (CS1056); stray keyword prefixes like `tnamespace` (CS1513); lambda chains closed with `{){` (CS1026); stuttered duplicate signature openers. Each covered by a named reflex.
5. **[Makefile escape artifacts](makefile-escape-artifacts.md)** — recipe lines need a literal TAB; lean-retry emits literal `\n`, `\t`, `\@`. Covered by the makefile reflex family.
6. **[Degenerate repetition](degenerate-repetition.md)** — `print(f"{task[print(f"{task[…`; fought at the sampler (`MU_REPEAT_PENALTY`) and by the degeneration guard (`MU_DEGEN_GUARD`). Not reflex-recoverable. Top residual failure.
7. **[C forward declarations / nested definitions](c-forward-declarations.md)** — `call to undeclared function`; `function definition is not allowed here`. Distillation names both; no scan reflex yet.

### Group 2 — Full-stack orchestration / multi-file

8. **[C# / ASP.NET scaffolding](csharp-aspnet-scaffolding.md)** — test csproj, EF Core/SQLite/ASP.NET package refs, NU1202 TFM mismatch, CS0017 duplicate entry point, CS0101 duplicate types, MSB1003 missing project. **p10 remains 0-pass** (run 7: CS0101 ×14, MSB1003 ×8, CS0053 ×8) — cascading CS errors, repair oscillates.
9. **[Vue / Vitest / Jest setup](vue-vitest-jest-setup.md)** — Jest `_test.js` naming → "No tests found"; missing `globals:true`; vitest watch-mode hang; missing `vue` peer dep; jest globals undefined when run via plain `node` instead of `npx jest`. Each covered by a named reflex or hint.
10. **[Build-target inconsistency & misplaced files](build-target-inconsistency.md)** — plans name entry-point targets the build file never defines; lean-retry writes files to wrong subdirs. Mitigated by relocation + stale-file cleanup.
11. **[Repair-context budget](repair-context-budget.md)** — the loaded window bounds prompt + generation together; large skill stacks and accumulated repair history overflow it (HTTP 400). Mitigated by lean repair system, `_strip_ansi`, `_fit_prompt_budget`, a 1536-token generation reserve, and chat()-level prompt shrinking (`_shrink_oversized`).

### Group 3 — Model ceiling

12. **[Test isolation design](test-isolation-design.md)** — model omits `beforeEach/afterEach`; shared state leaks across tests. [`fix_js_env_data_file`](../../src/mu/reflexes/javascript/fix_js_env_data_file.py) enables isolation when the model writes the hooks; ~50% pass.
13. **[Stateful-backend lifecycle rewrites](stateful-backend-lifecycle.md)** — Flask per-operation `sqlite3.connect` vs `:memory:` destroys data each call. Needs architectural rewrite beyond the 7B repair loop.
14. **[Missing imports](missing-imports.md)** — Python omits the import of the module under test (`NameError`); `ModuleNotFoundError` on `app`/`main`; missing C# `using`. Partly patched; still frequent.
15. **[Incorrect test assertions](incorrect-test-assertions.md)** — wrong values, undeclared mock data, `KeyError` on JSON response, endpoint not defined, bad CLI args. Test-design quality; not reflex-recoverable.

### Group 4 — Harness / environment

16. **[Environment hygiene](environment-hygiene.md)** — system-wide vs Homebrew Python (use venvs); server port already in use; empty session log → no distillable cause.
17. **[Syntax errors in test files](test-file-syntax-errors.md)** — JS same-scope `const` re-declaration (was mislabeled "Jest ESM") and `.[0]` member access ([`fix_js_same_scope_redeclaration`](../../src/mu/reflexes/javascript/fix_js_same_scope_redeclaration.py), [`fix_js_dot_bracket_access`](../../src/mu/reflexes/javascript/fix_js_dot_bracket_access.py)); C# stuttered method-signature openers ([`fix_csharp_consecutive_duplicate_signatures`](../../src/mu/reflexes/csharp/fix_csharp_consecutive_duplicate_signatures.py)).

18. **Test state leaks across runs**
  - Tests sharing mutable storage accumulate state between invocations; require setup/teardown that isolates state per test.

19. **Duplicate type definitions**
  - Ensure that types are not defined more than once in the same namespace to avoid conflicts and build errors.

20. **Stuck in a loop of repeated actions**
  - Repeatedly resolving module dependencies and applying reflexes can lead to a stuck state if the underlying issue is not addressed. Ensure that each action moves progress forward rather than repeating previous steps.

