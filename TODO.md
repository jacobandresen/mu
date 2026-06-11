# TODO — ranked by impact

Evidence base: `mu observe` + `mu kb` combination report (n≈900 sessions, qwen2.5),
CHALLENGES.md, KB_BASELINE.md. Refreshed 2026-06-10.

---

## 1. Ablate `fix_inline_recipe` — measure Δ and record into `reflex.efficacy`

**Why:** combination report shows P=0.54 [0.45, 0.63] vs base 0.67 (n=113) — CI entirely
below base rate, already statistically distinguishable. After #1 lands (oscillation stopped),
re-measure to see if the reflex is now harmless or still net-negative.

**What to do:**
```sh
# baseline (3 seeds, 5 runs each)
MU_SEED=42 python3 -m mu.dojo measure p7-flask --runs 5 --emit-json /tmp/base_42.json
MU_SEED=0  python3 -m mu.dojo measure p7-flask --runs 5 --emit-json /tmp/base_0.json
MU_SEED=7  python3 -m mu.dojo measure p7-flask --runs 5 --emit-json /tmp/base_7.json
# disabled
MU_SEED=42 python3 -m mu.dojo measure p7-flask --runs 5 --disable fix_inline_recipe --emit-json /tmp/dis_42.json
# … repeat for seeds 0, 7
```
Then `reflexdb.record_efficacy('fix_inline_recipe', ...)`. If `sz5_gate(deltas)` returns
True with positive Δ → remove the reflex.

---

## 2. Ablate `fix_inline_recipe` after oscillation fix lands in session data

**Why:** Before the oscillation fix, `fix_inline_recipe` had P=0.54 vs base 0.67 (CI entirely
below base). After the fix, re-measure to see if it's now harmless or still net-negative. The
oscillation burned repair passes on both reflexes — the true Δ is not known until clean data.

**What to do:** after ≥50 new sessions accumulate post-oscillation-fix (2026-06-11+), run:
```sh
MU_NUM_CTX=6000 MU_SEED=42 python3 -m mu.dojo measure p7-flask -n 5 --emit-json /tmp/base_42.json
MU_NUM_CTX=6000 MU_SEED=0  python3 -m mu.dojo measure p7-flask -n 5 --emit-json /tmp/base_0.json
MU_NUM_CTX=6000 MU_SEED=7  python3 -m mu.dojo measure p7-flask -n 5 --emit-json /tmp/base_7.json
# then with fix_inline_recipe disabled:
MU_NUM_CTX=6000 MU_SEED=42 python3 -m mu.dojo measure p7-flask -n 5 --disable fix_inline_recipe --emit-json /tmp/dis_42.json
# repeat seeds 0, 7
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

## Done (archived)

- **`fix_js_const_reassignment`** — implemented in `javascript.py` (test-out, p8-node)
- **`fix_vue_attr_quotes`** — implemented in `javascript.py` (scan, p9-vue)
- **`fix_makefile_missing_test_target`** — implemented in `makefile.py`
- **`fix_dotnet_test_cwd`** — implemented in `makefile.py` (p10-dotnet)
- **KB Iter 3: shared-core refactor** — `_fix_duplicate_decls` in `core.py`, iter 3 commit 48f995a
- **KB Iters 4–5** — composite chains + validation tests, commits 4746d22, 25f3d3e
- **Reduce no-distilled-cause** — added 7 new patterns to `diagnose.py` + `observe.py` blank-log/no-log handlers; qwen2.5 bucket dropped 120→24
- **Oscillation fix** — `fix_inline_recipe` guard extended to `declared | _KNOWN_TARGETS`; regression test added (`test_inline_recipe_oscillation.py`)
- **`fix_sqlite_conn_scope`** — adds `cursor = conn.cursor()` at module level when conn is top-level but cursor is missing; fires only when test imports cursor; 6 tests
- **`fix_dotnet_test_cwd` extended** — now also handles `dotnet test tests/` where `tests/` has no `.csproj` (the MSB1003 source for 67 sessions)
- **p5-gin archiving** — resolved; 0 sessions with missing project_dir as of 2026-06-11
