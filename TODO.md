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

## 3. Jest ESM configuration reflex (18 qwen2.5 sessions)

**Why:** `mu observe` shows 18 sessions with "Jest: ESM/CJS parse error" — second largest
distillable bucket after MSBuild. Pattern: LLM writes ES module JS (import/export) but Jest
config lacks ESM transform.

**What to do:** Reflex in `javascript.py`: if package.json has `jest` config without transform
for `.js` files, and test log has `Jest encountered an unexpected token`, add
`"type": "module"` to package.json and `"testEnvironment": "node"` to jest config.
Or: change jest command to `NODE_OPTIONS='--experimental-vm-modules' npx jest`.

---

## Done (recent)

- **Oscillation fix** — `fix_inline_recipe` guard extended to `declared | _KNOWN_TARGETS`; regression test added
- **`fix_dotnet_test_cwd` extended** — handles `dotnet test tests/` where `tests/` has no `.csproj` (MSB1003, 67 sessions)
- **`fix_js_duplicate_const`** — removes consecutive duplicate const/let in test files
- **`fix_js_program_parse_guard`** — wraps `program.parse(process.argv)` with `require.main === module`
- **Reflex KB** — catalog + schema + model profiles + Beta-Binomial posteriors + ablation + combination report + shared-core refactor + validation tests (iters 1–5)
- **Repair-loop degeneration → architect escalation** — same distilled error ≥2 passes → `_run_architect_pass()`
