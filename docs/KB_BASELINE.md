# Reflex KB Baseline

This document records dated baseline snapshots for the Reflex KB plan.

| Date | Iteration | Pass Rate | Avg Repair Iters | First‑Try Rate | Tokens/Call | Top‑3 Candidate Signatures |
|------|-----------|----------|------------------|----------------|-------------|------------------------------|
| 2026‑06‑05 | Step 0 (baseline) | 67.3% (35/52) | 1.9 | 54% | 21,265 | `Makefile: no rule to make target 'X'`, `output assertion failed — expected: Any<String>, "[`, `SyntaxError: Invalid end tag.` |
| 2026‑06‑07 | Iter 1 (test harness) | 67.5% (560/830 cumul.) | 1.9 | 60% | 17,832 | `SyntaxError: Duplicate attribute` (p9-vue, 2×), `MSBuild MSB1003` (p10-dotnet, chronic), `cannot import name 'conn' from 'main'` (p2-sqlite) |

## Iter 1 RIP findings — 2026‑06‑07

**Change:** Added `test_reflex_idempotency.py` + `tests/fixtures/missing_bracket.json`. No runtime change.

**Regression check:** No regression. Overall rate flat (67.3%→67.5%, noise). Avg repair iters 1.9 unchanged. Tokens/call +75 (flat). Second-batch per-round trend 7→6→5→4 successes — within stochastic noise at N≈9 problems/round.

**Model feedback (CHALLENGES.md #18–20):**
- #18 Incorrect imports: `cannot import name 'conn'/'cursor' from 'main'` — p2-sqlite; model puts module-level db objects that tests import by name.
- #19 Incorrect mock expectations: Jest mock factory mismatch — p8-node.
- #20 Duplicate attribute in HTML: `SyntaxError: Duplicate attribute` — p9-vue.

**Candidate ranking:** `SyntaxError: Duplicate attribute` recurs in p9-vue (rounds 3+4), but is single-problem → fails §0 ≥2-problem threshold. `MSBuild MSB1003` is chronic but single-problem and not scan-reflex-addressable. No candidate clears the generality gate.

**Go/no-go:** Clean no-regression run. Ready for **Iteration 2** (schema fields + efficacy storage). Note: "frozen no-regression smoke" (known-bad fixtures → pinned output) is partially complete — only `missing_bracket.json` exists; can expand incrementally.
