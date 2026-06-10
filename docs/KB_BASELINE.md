# Reflex KB Baseline

This document records dated baseline snapshots for the Reflex KB plan.

| Date | Iteration | Pass Rate | Avg Repair Iters | First‑Try Rate | Tokens/Call | Top‑3 Candidate Signatures |
|------|-----------|----------|------------------|----------------|-------------|------------------------------|
| 2026‑06‑05 | Step 0 (baseline) | 67.3% (35/52) | 1.9 | 54% | 21,265 | `Makefile: no rule to make target 'X'`, `output assertion failed — expected: Any<String>, "[`, `SyntaxError: Invalid end tag.` |
| 2026‑06‑07 | Iter 1 (test harness) | 67.5% (560/830 cumul.) | 1.9 | 60% | 17,832 | `SyntaxError: Duplicate attribute` (p9-vue, 2×), `MSBuild MSB1003` (p10-dotnet, chronic), `cannot import name 'conn' from 'main'` (p2-sqlite) |

| 2026‑06‑10 | Iter 2 (schema + efficacy) | 69.3% (813 sessions, qwen2.5) | 1.9 | 62% | 17,832 | `MSBuild MSB1003` (p10-dotnet, chronic single-problem), `Makefile: no rule to make target 'X'` (multi-problem, 15×), `assertion failed` (p8-node, 11×) |
| 2026‑06‑10 | Iter 3 (shared-core refactor) | — (behavior-preserving; byte gate) | — | — | — | no change — pure refactor |
| 2026‑06‑10 | Iter 4a (centralize chains, Part 1) | — (behavior-preserving; sequence-preserved) | — | — | — | no change — pure refactor |
| 2026‑06‑10 | Iter 5 (validation + interaction model) | — (no-regression; new tests only) | — | — | — | no change — tests + honesty audit + interaction model |

## Iter 5 RIP findings — 2026‑06‑10

**Change:** Validation discipline + interaction model (§11).
- `tests/test_calibration.py`: Beta-Binomial coverage ≥88% verified at p=0.3/0.5/0.7, N=500 sims, seeded RNG.
- `tests/test_ablation_rule.py`: sz5_gate() keep/revert/boundary/purity contract — 8 cases.
- `reflexdb.honesty_audit()`: flags reflexes with ≥90% of firings in one problem_id (≥5 sessions); appended to `mu kb report()`.
- `tests/test_honesty_audit.py`: 6 cases (concentration/distribution/min-n/null-problem/empty).
- `src/mu/interaction.py`: DiscreteBayesianNetwork over co-occurrence edges (≥3 co-fires); §10 leak guard tested by inspection.
- pgmpy==1.1.2 installed; required (not optional) per user instruction.

**Regression check:** No regression. 70/70 tests pass. No runtime change. TRP pending (blocked on PID 25903 TRP; same constraint as Iter 4 Part 2).

**Go/no-go:** Clean. Ready for Iter 4 Part 2 (offline order bake) and final TRP once model is free.

## Iter 4a RIP findings — 2026‑06‑10

**Change (Part 1 — centralize):** Extracted per-language chain functions from scattered agent.py call sites:
- `apply_csharp_write_reflexes` / `apply_csharp_repair_reflexes` in `csharp.py`
- `apply_js_write_reflexes` / `apply_js_repair_reflexes` in `javascript.py`
- `apply_rust_source_reflexes` in `rust.py`
All registered in `_CATALOG` under `'composite-chain'`. Python excluded (sibling-loop logic, too complex). `or`-chain at agent.py ~858 preserved exactly (short-circuit composition mode, mixed languages).

**Part 2 (bake order) deferred:** Blocked — iter-3 TRP (PID 25903) still running; two concurrent qwen runs thrash M2 8GB. A/B data across ≥3 seeds needed; will run after TRP completes.

**Regression check:** Behavior-preserving by construction. Same reflexes, same sequence, same composition modes (sequential single-shot for write/repair; the fixpoint `run_reflexes` and `or`-chain left untouched). 47/47 tests pass. TRP pending.

**Go/no-go for Part 1:** Clean. Part 2 blocked until TRP completes and iter-3/4 TRP results reviewed.

## Iter 3 RIP findings — 2026‑06‑10

**Change:** Extracted `_fix_duplicate_decls` into `core.py` as a shared keep-first dedup kernel. `fix_rust_duplicate_use` and `fix_js_duplicate_require` refactored to thin wrappers. `fix_csharp_duplicate_classes` excluded — cross-file brace-depth algorithm, not line-dedup, different class.

**Regression check:** Behavior-preserving by construction. 10-case byte-diff battery (back-to-back, non-adjacent, no-trailing-newline, CRLF, no-fire for both Rust+JS) — all byte-identical before/after. 47/47 tests pass. TRP in progress (PID 25903); by design cannot show regression.

**Go/no-go:** Clean. Ready for **Iteration 4** (offline-baked chain order).

## Iter 2 RIP findings — 2026‑06‑10

**Change:** Schema fields (`artifact`, `phase`, `idempotent`, `risk`, `evidence`) on `ReflexRecord` + SQLite reflex table; `phase`/`ts` added to `firing` table; new `efficacy_run` table; `sz5_gate()` + `record_efficacy()` in `reflexdb`; `--emit-json` on `mu dojo measure`. 30 reflex annotations in `_ANNOTATIONS`; 3 scan/file reflexes measured idempotent in `idempotent_ids.txt`. No runtime change.

**Regression check:** No regression — pure metadata iteration. Pass rate 0.693 (n=813) vs 0.675 prior snapshot (noise; 3 sessions added). Avg repair iters 1.9 unchanged. Tokens/call 17,832 unchanged. Storage tested offline: 47/47 tests pass including all `test_efficacy.py` cases.

**Schema findings:** `mu kb` combination report now shows `risk` tags on the ablation shortlist. Notable: `fix_inline_recipe` (P=0.54 [0.45,0.63] vs base 0.69, n=112) — CI entirely below base rate, i.e. sessions where it fires have lower success. It is annotated `risk='medium'` by the new schema. This is the strongest signal in the combination report and the first ablation target.

`fix_nested_targets` (fired 65 sessions) is on the shortlist with `risk=medium` tag. `fix_missing_venv_rule` (95 sessions) and `fix_makefile_recipe_is_prerequisite_list` (91 sessions) are top-of-shortlist but `risk=low`.

**Model feedback (from prior sessions; new TRP round 1 in progress):**
- `MSBuild MSB1003` (58×, p10-dotnet): chronic, single-problem, not scan-reflex-addressable.
- `Makefile: no rule to make target 'X'` (15×): multi-problem, could motivate a reflex — but `fix_makefile_binary_name` already handles some cases; needs closer look.
- `assertion failed: expected 'X' to contain 'X'` (11×, p8-node): Jest assertion mismatch, single-problem.

**Ablation target:** `fix_inline_recipe` — risk=medium, CI below base rate (already statistically distinguishable misfire in combination report). **Pending:** run `mu dojo measure p7-flask --runs 5 --seed 42 --emit-json` (baseline + `--disable fix_inline_recipe`) after TRP completes, then `reflexdb.record_efficacy()` across ≥3 seeds for §5z gate. First seed started after next TRP autocommit.

**Go/no-go:** Clean no-regression. Ready for **Iteration 3** (shared-core refactor). Ablation of `fix_inline_recipe` to run between iterations as a background task; first Δ will be recorded into `reflex.efficacy` before iter-3 commit.

## Iter 1 RIP findings — 2026‑06‑07

**Change:** Added `test_reflex_idempotency.py` + `tests/fixtures/missing_bracket.json`. No runtime change.

**Regression check:** No regression. Overall rate flat (67.3%→67.5%, noise). Avg repair iters 1.9 unchanged. Tokens/call +75 (flat). Second-batch per-round trend 7→6→5→4 successes — within stochastic noise at N≈9 problems/round.

**Model feedback (CHALLENGES.md #18–20):**
- #18 Incorrect imports: `cannot import name 'conn'/'cursor' from 'main'` — p2-sqlite; model puts module-level db objects that tests import by name.
- #19 Incorrect mock expectations: Jest mock factory mismatch — p8-node.
- #20 Duplicate attribute in HTML: `SyntaxError: Duplicate attribute` — p9-vue.

**Candidate ranking:** `SyntaxError: Duplicate attribute` recurs in p9-vue (rounds 3+4), but is single-problem → fails §0 ≥2-problem threshold. `MSBuild MSB1003` is chronic but single-problem and not scan-reflex-addressable. No candidate clears the generality gate.

**Go/no-go:** Clean no-regression run. Ready for **Iteration 2** (schema fields + efficacy storage). Note: "frozen no-regression smoke" (known-bad fixtures → pinned output) is partially complete — only `missing_bracket.json` exists; can expand incrementally.
