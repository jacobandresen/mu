# TODO — ranked by impact

Evidence base: `dojo-failures.md` rounds 1–4 (2026-06-07) + round 1 (2026-06-10),
`mu kb` combination report (n=855 sessions), CHALLENGES.md.

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
MU_SEED=42 N=5 python3 -m mu.dojo measure p7-flask --emit-json /tmp/base_42.json
MU_SEED=0  N=5 python3 -m mu.dojo measure p7-flask --emit-json /tmp/base_0.json
MU_SEED=7  N=5 python3 -m mu.dojo measure p7-flask --emit-json /tmp/base_7.json
# disabled
MU_SEED=42 N=5 python3 -m mu.dojo measure p7-flask --disable fix_inline_recipe --emit-json /tmp/dis_42.json
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

## 5. Reflex: fix `const` → `let` on assignment error (`fix_js_const_reassignment`)

**Why:** `TypeError: Assignment to constant variable` recurs in p8-node (rounds 2+).
Clear deterministic fix: find the `const X` declaration that is later reassigned.

**What to do:** add a `test-out` reflex in `src/mu/reflexes/javascript.py`. When test output
contains `TypeError: Assignment to constant variable`, scan `.js` files for `const \w+` that
appear in an assignment on a later line and change `const` to `let`. Add an idempotency test.

---

## 6. Reflex: strip invalid characters from Vue HTML attribute names (`fix_vue_attr_quotes`)

**Why:** `SyntaxError: Attribute name cannot contain U+0022 ("), U+0027 ('), and U+003C (<)`
appeared in p9-vue in the current (2026-06-10) round. CHALLENGES #22.

**What to do:** add a scan reflex in `src/mu/reflexes/javascript.py` that processes `.vue`
files, finds attribute names containing `"`, `'`, or `<` in the `<template>` section, and
strips or replaces them. Existing `fix_vue_*` family for reference.

---

## 7. Reflex: add missing `test:` Makefile target (`fix_makefile_missing_test_target`)

**Why:** `Makefile: no rule to make target 'test'` appears in p7-flask rounds 1 and 3 of the
2026-06-07 run. The model generates a Makefile without a `test:` phony. An existing reflex
family handles related patterns (`fix_makefile_bare_pytest`, `fix_missing_venv_rule`).

**What to do:** add a scan reflex in `src/mu/reflexes/makefile.py`. If the Makefile has no
`test:` target but has a `.venv/bin/pytest` invocation (or `npm test`, `cargo test`, etc.),
insert a `test:` target delegating to the appropriate command. Generalises across toolchains.

---

## 8. Reflex: fix `dotnet test` without project path (`fix_dotnet_test_cwd`)

**Why:** `MSBuild MSB1003: Specify a project or solution file. The current working directory
does not contain a project` appears in p10 in every round (58× in candidate signatures).
The model writes `dotnet test` in the Makefile from the repo root instead of `cd Tests && dotnet test`.

**What to do:** add a scan reflex in `src/mu/reflexes/csharp.py` (or `makefile.py`). If a
Makefile line contains `dotnet test` without a path argument and a `.csproj` file exists in a
subdirectory, rewrite to `dotnet test <subdir>/<project>.csproj`.

---

## 9. Improve `diagnose.py` coverage for "no distilled cause"

**Why:** 67 of 210 qwen2.5 failures have `(no distilled cause)` — the largest single bucket.
These sessions can't contribute to `mu observe` candidates. The gaps are primarily Go errors,
general assertion failures, and early-exit crashes with no test log.

**What to do:** audit the 67 sessions — read 5–10 `logs/tests*.log` files from sessions with
no cause. Add regex patterns to `distill_test_errors()` in `src/mu/diagnose.py` for Go compile
errors (`undefined:`, `cannot use`), generic assertion failures, and empty-log handling.
Validate: re-run `mu observe` and check if count drops below 40.

---

## 10. KB Iteration 3: shared-core refactor for duplicate-declaration family

**Why:** `fix_rust_duplicate_use`, `fix_js_duplicate_require`, `fix_csharp_duplicate_classes`
are three copies of the same algorithm (find duplicate declarations, keep first, drop rest)
with per-language regex. Per REFLEX_KB_PLAN.md iter-3.

**What to do:** extract a `_fix_duplicate_declarations(path, pattern, keep_fn)` core in
`src/mu/reflexes/core.py`. Thin wrappers in rust/javascript/csharp call it with their regex.
Gate: iter-1 idempotency tests + frozen output tests must stay byte-identical. Run TRP after.
