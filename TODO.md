# TODO — ranked by impact

Evidence base: per-problem run-7 data (`docs/p*.md` "Last measured"), repair-trace
mining, `mu kb` combination report. Refreshed 2026-06-13 (after run 7, 8 h / 12 rounds,
qwen2.5-coder-7b).

---

## Open — ranked by impact

1. **p10 full-stack (0/12 — the open problem).** Multi-project C#/Vue —
   challenge [csharp-aspnet-scaffolding](docs/challenges/csharp-aspnet-scaffolding.md).
   Dominant run-7 errors: CS0101 duplicate types across files (×14), MSB1003 no
   project/solution at the test dir (×8), CS0053 inconsistent accessibility on EF types
   (×8). Mix of scaffolding (staged-plan type dedup; ensure `dotnet test` sees a
   csproj/solution) and model ceiling (cascading errors, repair oscillates). Biggest gap.
   **Lead proposal:** template scaffolding at ground time — plan
   [docs/plans/scaffolding.md](docs/plans/scaffolding.md) (offline-first; `dotnet new`
   offline, Vite online-opt-in with vendored fallback).
2. **p8 jest globals** — challenge [vue-vitest-jest-setup](docs/challenges/vue-vitest-jest-setup.md).
   `describe/test/it/jest is not defined` — tests run under plain `node`, not jest. The
   package.json-script half is now deterministic (`fix_package_json_bare_jest` rewrites both
   `"test": "jest"` and `"test": "node x.test.js"` → `npx jest`); residual is when the model
   hard-codes `node x.test.js` in a **Makefile** recipe (no jest binary there either) — extend
   `fix_makefile_npm_test_jest` to that shape if it recurs. The remaining p8 failures are
   model-ceiling module-contract bugs (`program.add is not a function`).
3. **p2 SQLAlchemy ORM setup (9/15)** — challenge [missing-imports](docs/challenges/missing-imports.md).
   `Todo has no attribute '__table__'`, `declarative_base` undefined — declarative-base
   wiring done wrong. Candidate: a python-writer skill rule, or a reflex for the standard
   declarative-base shape.
4. **p9 component/test contract (12/13)** — challenge [incorrect-test-assertions](docs/challenges/incorrect-test-assertions.md).
   Assertion mismatches (component renders heading + button, not the todo text). Mostly
   model quality — low priority, accept variance.

---

## Done (recent)

- **False-pass honesty fix + p7 Makefile grounding (2026-06-19).** Archive mining found
  p7-flask was being scored **success** ~9× while running zero tests: the planner names
  `make test` with no Makefile, `ground_plan` Level 2b synthesized a **C** `cc -o main main.c`
  template (Python project!), the makefile reflexes hoisted the bogus rule out, and
  `make test` printed `make: Nothing to be done for 'test'.` → exit 0 → the gate certified a
  pass though nothing ran. Two fixes, both regression-tested:
  - **plan.py** — Level 2b's `cc -o` fallback now fires only when the plan has real C/C++
    sources; a Python project falls through to Level 4a (the venv Makefile with a real
    `test:` target). Verified live: p7 now genuinely passes (`1 passed` from pytest).
  - **agent.py** — `_test_passed`/`_make_vacuous` reject a make-only test command that
    reports "Nothing to be done" (no work ran) at all four test-gate sites. `make && ./bin`
    (p1/p3) is gated by the binary's own exit code and is left untouched. A test gate must
    witness tests execute. (`test_ground_plan_makefile.py`, `test_vacuous_make_gate.py`.)
- **p8 jest-globals: node-invoked spec (2026-06-19).** Extended `fix_package_json_bare_jest`
  to also rewrite `"test": "node todo.test.js"` → `npx jest --forceExit` (jest globals are
  undefined under bare node → "ReferenceError: it is not defined"). (`test_jest_node_invocation.py`.)

- **Round 7 (2026-06-13), telemetry-driven.** `fix_csharp_test_program_conflict` (CS0017
  test-SDK second `Main`); `fix_python_unindented_body` (lint-driven, ast-rollback);
  test-gate creates a missing `Cargo.toml`; jest-globals diagnose hint. Reflex telemetry:
  complete `firings.jsonl` (`core.noted` wraps all direct call sites), `reflex_diffs.jsonl`,
  `repair_trace.jsonl`. **Crash fix:** round-7 reflexes were wired into `agent.py` but not
  imported → NameError crashed every problem's repair loop (wasted run 8); fixed + AST guard
  (`test_agent_reflex_imports`) + launcher preflight (test suite + live smoke before any 8 h run).

- **`fix_inline_recipe` ablation (2026-06-11, TODO #1) — KEEP.** 3 seeds × 5 runs on
  p7-flask, baseline vs `--disable fix_inline_recipe`, 245 post-oscillation-fix sessions in
  the archive. Per-seed Δ (disabled − baseline): −0.20, 0.00, 0.00; mean Δ −0.067;
  `sz5_gate` False (95% CI includes 0). Disabling did not help — the only pass in 30 runs
  was a baseline run — so the old net-negative signal (P=0.54 [0.45,0.63] vs base 0.67,
  n=113) was the oscillation itself, fixed by the `declared | _KNOWN_TARGETS` guard.
  Recorded in `efficacy_run` (3 rows) and `reflex.efficacy` = −0.067.
  Note: p7-flask fresh-plan pass rate measured far below the old 0.67 base rate (1/15
  baseline) — that base rate mixed plan-regen runs; don't compare across measurement modes.

- **"Jest ESM" bucket resolved (2026-06-11)** — the 18-session "Jest: ESM/CJS parse error"
  bucket was *mislabeled*: diagnose's banner rule ("Jest encountered an unexpected token")
  matched before the Babel `SyntaxError` detail line, so every Jest parse failure — none of
  which were actually ESM — got the ESM label. Three fixes:
  - `diagnose.py` weak-rule mechanism: banner hints survive only when no specific grammar
    matched; added a generic Babel `SyntaxError: file: msg (L:C)` rule and a real-ESM rule
    (`Cannot use import statement outside a module`). Replayed against all 19 archived
    banner sessions: each now distills to its specific cause.
  - `fix_js_same_scope_redeclaration` — the dominant real pattern (10+ sessions):
    `const todos = readTodos();` re-declared mid-test-block. Converts the re-declaration to
    an assignment and promotes the first decl to `let`; brace-depth scope tracking leaves
    legal shadowing alone. (`fix_js_duplicate_const` only handled *consecutive* duplicates.)
  - `fix_js_dot_bracket_access` — `).[0].id` member access (2 sessions); deletes the stray
    dot, leaves `?.[` / `...[` alone.
- **Oscillation fix** — `fix_inline_recipe` guard extended to `declared | _KNOWN_TARGETS`; regression test added
- **`fix_dotnet_test_cwd` extended** — handles `dotnet test tests/` where `tests/` has no `.csproj` (MSB1003, 67 sessions)
- **`fix_js_duplicate_const`** — removes consecutive duplicate const/let in test files
- **`fix_js_program_parse_guard`** — wraps `program.parse(process.argv)` with `require.main === module`
- **Reflex KB** — catalog + schema + model profiles + Beta-Binomial posteriors + ablation + combination report + shared-core refactor + validation tests (iters 1–5)
- **Repair-loop degeneration → architect escalation** — same distilled error ≥2 passes → `_run_architect_pass()`
