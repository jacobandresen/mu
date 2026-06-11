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

## 2. Fix p5-gin (Go) sessions archiving as `unknown` with `project_dir: None`

**Why:** every round has 1–2 p5-gin sessions labelled `unknown`. `mu observe` shows p5-gin
failure rate 0.19 (n=84) — that 19% may be partially masked by archiving failures.

**What to do:** run `mu dojo run p5-gin` manually with logging, find where the session starts
without a project dir. Check `dojo/runner.py` and `archive.py` for the code path that leaves
`project_dir` unset on early exit.

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
