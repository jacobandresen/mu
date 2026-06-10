# TODO — ranked by impact

Evidence base: `mu observe` + `mu kb` combination report (n≈900 sessions, qwen2.5),
CHALLENGES.md, KB_BASELINE.md. Refreshed 2026-06-10.

---

## 1. Fix `fix_inline_recipe` / `fix_makefile_recipe_is_prerequisite_list` oscillation

**Why it's #1:** sequence data shows symmetric ping-pong: each fires after the other ×93,
burning all repair passes on Makefile churn. Root cause identified: `fix_inline_recipe`
uses `declared` for its guard, `fix_makefile_recipe_is_prerequisite_list` uses
`declared | _KNOWN_TARGETS`. When `install`/`test` are in `_KNOWN_TARGETS` but not
declared as targets, the two reflexes undo each other every pass.

**Fix:** In `fix_inline_recipe` line 182, change:
```python
if all(w in declared for w in after.split()):
```
to:
```python
if all(w in (declared | _KNOWN_TARGETS) for w in after.split()):
```
This makes the prerequisite-list guard use the same set as `fix_makefile_recipe_is_prerequisite_list`.
Add idempotency test: two back-to-back applies produce the same output.

Files: `src/mu/reflexes/makefile.py:182`.

---

## 2. Ablate `fix_inline_recipe` — measure Δ and record into `reflex.efficacy`

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

## 3. Reduce "no distilled cause" (85 qwen2.5 failures, largest bucket)

**Why:** `mu observe` shows 85/~290 qwen2.5 failures have `(no distilled cause)` + 42 blank
causes — together that's ~44% of failures invisible to the candidate-reflex pipeline. The
immediately actionable bucket is Go syntax errors (10×: `unexpected ., expected }`).

**What to do:**
- Add `Go syntax error: unexpected X, expected Y` patterns to `distill_test_errors()` in
  `src/mu/diagnose.py`. Also handle blank test log (empty `logs/tests*.log`) — return a
  generic "test log empty" cause rather than blank/None.
- Check 5–10 `(no distilled cause)` sessions manually: `ls ~/.mu/sessions | tail -20` then
  read `logs/tests*.log` from sessions with blank cause.
- Target: drop "no distilled cause" below 50 sessions.

---

## 4. Reflex: fix module-level SQLite connection (`fix_sqlite_conn_scope`)

**Why:** `cannot import name 'conn' from 'main'` recurs in p2-sqlite (9 sessions, 3rd in
observe output). Multi-session, deterministic, within one problem — meets ≥2-session threshold
for a scan reflex even if single-problem, because the pattern is general Python.

**What to do:** add a scan reflex in `src/mu/reflexes/python.py` that detects a module-level
`conn = sqlite3.connect(...)` or `cursor = conn.cursor()` and wraps it in a `get_connection()`
factory function. Test: fixture with the pattern, assert reflex fires and result is importable.

---

## 5. Fix p5-gin (Go) sessions archiving as `unknown` with `project_dir: None`

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
