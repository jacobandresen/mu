# TODO — ranked by impact

Evidence base: `dojo-failures.md` + `mu kb` combination report (n=855+ sessions),
CHALLENGES.md, KB_BASELINE.md.

---

## 1. Fix `fix_inline_recipe` / `fix_makefile_recipe_is_prerequisite_list` oscillation

**Why it's #1:** firing data shows these two reflexes ping-ponging on every repair pass
(pattern: `fix_inline_recipe:1 | fix_makefile_recipe_is_prerequisite_list:1 | fix_inline_recipe:2 | …`)
in 92 sessions, burning all 4 repair passes on Makefile churn instead of the actual failure.
Most of those sessions end in failure. This is the single most wasteful behavior in the system.

**What to do:** read both functions side-by-side and find what each produces that triggers the
other. Add an idempotency guard (e.g. skip `fix_inline_recipe` if the file already has a
properly-separated recipe), or merge the two into one pass that handles both patterns.

Files: `src/mu/reflexes/makefile.py` — `fix_inline_recipe`, `fix_makefile_recipe_is_prerequisite_list`.

---

## 2. Ablate `fix_inline_recipe` — measure Δ and record into `reflex.efficacy`

**Why:** combination report shows P=0.54 [0.45, 0.63] vs base 0.67 (n=113) — CI entirely
below base rate, already statistically distinguishable. Together with #1, this is the
strongest signal of a harmful reflex.

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
Then `reflexdb.record_efficacy('fix_inline_recipe', ...)` for each seed. If `sz5_gate(deltas)`
returns True with positive Δ → remove the reflex.

---

## 3. Fix p5-gin (Go) sessions archiving as `unknown` with `project_dir: None`

**Why:** every round has 1–2 p5-gin sessions labelled `unknown` in the per-problem summary.
`meta.json` shows `project_dir: None, outcome: unknown` — the session never properly starts
or archives. This masks Go failures and inflates the "no distilled cause" count.

**What to do:** run `mu dojo run p5-gin` manually with logging, find where the session starts
without a project dir. Check `dojo/runner.py` and `archive.py` for the code path that leaves
`project_dir` unset on early exit.

---

## 4. Reflex: fix module-level SQLite connection (`fix_sqlite_conn_scope`)

**Why:** `cannot import name 'conn' from 'main'` / `cannot import name 'cursor' from 'main'`
recurs in p2-sqlite across 9 sessions. The model puts `conn = sqlite3.connect(...)` at
module level; the test tries to `from main import conn`. CHALLENGES #13/#18.

**What to do:** add a scan reflex in `src/mu/reflexes/python.py` that detects a module-level
`conn = sqlite3.connect(...)` or `cursor = conn.cursor()` and wraps it in a `get_connection()`
factory function. Test: fixture with the pattern, assert reflex fires and result is importable.

---

## 5. Improve `diagnose.py` coverage for "no distilled cause"

**Why:** 67 of 210 qwen2.5 failures have `(no distilled cause)` — the largest single bucket.
These sessions can't contribute to `mu observe` candidates. The gaps are primarily Go errors,
general assertion failures, and early-exit crashes with no test log.

**What to do:** audit the 67 sessions — read 5–10 `logs/tests*.log` files from sessions with
no cause. Add regex patterns to `distill_test_errors()` in `src/mu/diagnose.py` for Go compile
errors (`undefined:`, `cannot use`), generic assertion failures, and empty-log handling.
Validate: re-run `mu observe` and check if count drops below 40.

---

## Done (archived)

- **`fix_js_const_reassignment`** — implemented in `javascript.py` (test-out, p8-node)
- **`fix_vue_attr_quotes`** — implemented in `javascript.py` (scan, p9-vue)
- **`fix_makefile_missing_test_target`** — implemented in `makefile.py`
- **`fix_dotnet_test_cwd`** — implemented in `makefile.py` (p10-dotnet)
- **KB Iter 3: shared-core refactor** — `_fix_duplicate_decls` in `core.py`, iter 3 commit 48f995a
- **KB Iters 4–5** — composite chains + validation tests, commits 4746d22, 25f3d3e
