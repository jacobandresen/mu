# TODO — ranked by impact

Evidence base: `mu observe` + `mu kb` combination report (n≈1025 sessions, qwen2.5),
CHALLENGES.md. Refreshed 2026-06-11.

---

## Done (recent)

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
