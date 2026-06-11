# TODO — ranked by impact

Evidence base: `mu observe` + `mu kb` combination report (n≈1025 sessions, qwen2.5),
CHALLENGES.md. Refreshed 2026-06-11.

---

## 1. Ablate `fix_inline_recipe` — measure Δ and record into `reflex.efficacy`

**Why:** combination report shows P=0.54 [0.45, 0.63] vs base 0.67 (n=113) — CI entirely
below base rate, already statistically distinguishable. After #1 lands (oscillation stopped),
re-measure to see if the reflex is now harmless or still net-negative.

**What to do:** after ≥50 new sessions accumulate post-oscillation-fix (2026-06-11+), run:
```sh
# 3 seeds × 5 runs baseline (fresh plan each run — no --regen)
MU_NUM_CTX=6000 MU_SEED=42 python3 -m mu.dojo measure p7-flask -n 5 --emit-json /tmp/base_42.json
MU_NUM_CTX=6000 MU_SEED=0  python3 -m mu.dojo measure p7-flask -n 5 --emit-json /tmp/base_0.json
MU_NUM_CTX=6000 MU_SEED=7  python3 -m mu.dojo measure p7-flask -n 5 --emit-json /tmp/base_7.json
# then with fix_inline_recipe disabled:
MU_NUM_CTX=6000 MU_SEED=42 python3 -m mu.dojo measure p7-flask -n 5 --disable fix_inline_recipe --emit-json /tmp/dis_42.json
MU_NUM_CTX=6000 MU_SEED=0  python3 -m mu.dojo measure p7-flask -n 5 --disable fix_inline_recipe --emit-json /tmp/dis_0.json
MU_NUM_CTX=6000 MU_SEED=7  python3 -m mu.dojo measure p7-flask -n 5 --disable fix_inline_recipe --emit-json /tmp/dis_7.json
```
Call `reflexdb.record_efficacy('fix_inline_recipe', ...)`. If `sz5_gate(deltas)` is True with
positive Δ → remove the reflex.

---

## Done (recent)

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
