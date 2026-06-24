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

p10 lever A/Bs (MSB1003, entry-point, S2, build-order, TFM) are logged in
[`docs/ablations.md`](docs/ablations.md). Full narrative for each item below is in git
history + `docs/challenges/`; kept here as a one-line index.

- **False-pass honesty + p7 Makefile grounding (2026-06-19)** — p7-flask was scored success ~9× while running zero tests (`make test` → "Nothing to be done" → exit 0). `plan.py`: Level 2b `cc -o` fallback fires only with real C/C++ sources; `agent.py`: test gates reject "Nothing to be done" make commands. (`test_ground_plan_makefile.py`, `test_vacuous_make_gate.py`.)
- **p8 jest-globals node-invoked spec (2026-06-19)** — `fix_package_json_bare_jest` also rewrites `"test": "node x.test.js"` → `npx jest --forceExit`. (`test_jest_node_invocation.py`.)
- **Round 7 (2026-06-13), telemetry-driven** — `fix_csharp_test_program_conflict` (CS0017), `fix_python_unindented_body`, test-gate creates missing `Cargo.toml`. Reflex telemetry: `firings.jsonl`/`reflex_diffs.jsonl`/`repair_trace.jsonl`. Crash fix: unimported round-7 reflexes NameError'd the repair loop → AST guard `test_agent_reflex_imports` + launcher preflight.
- **`fix_inline_recipe` ablation (2026-06-11) — KEEP** — disabling didn't help (mean Δ −0.067, CI includes 0); the old net-negative signal was the oscillation, fixed by the `declared | _KNOWN_TARGETS` guard.
- **"Jest ESM" bucket resolved (2026-06-11)** — bucket was mislabeled (banner rule matched before the Babel detail). `diagnose.py` weak-rule mechanism + `fix_js_same_scope_redeclaration` + `fix_js_dot_bracket_access`.
- **`fix_dotnet_test_cwd` extended** — `dotnet test tests/` with no `.csproj` (MSB1003).
- **`fix_js_duplicate_const`** / **`fix_js_program_parse_guard`** — consecutive dup const/let in tests; `require.main === module` guard.
- **Reflex KB** — catalog + schema + profiles + Beta-Binomial posteriors + ablation + combination report + shared-core refactor (iters 1–5).
- **Repair-loop degeneration → architect escalation** — same distilled error ≥2 passes → `_run_architect_pass()`.
