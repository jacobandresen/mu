# Reflex KB — Implementation Plan (completed)

Five iterations on `kb-implementation`. Local model: `qwen2.5-coder-7b-instruct`,
`MU_NUM_CTX=6000`. TRP + RIP mandatory between each iteration.

## Status

| # | Iteration | Status | Commit |
|---|---|---|---|
| 0 | Baseline snapshot | ✓ | 8ff56e9 |
| 1 | Idempotency test harness | ✓ | a6798d3 |
| 2 | Schema fields + efficacy storage | ✓ | 53d6e06 |
| 3 | Shared-core refactor | ✓ | 48f995a |
| 4 | Offline-baked chain order | Part 1 ✓ (4746d22) / Part 2 pending TRP A/B | — |
| 5 | Validation discipline + interaction model | ✓ | 25f3d3e |

## Iter 4 Part 2 — remaining gate

Run `mu dojo measure --seed` A/B across ≥3 seeds. Keep new order only if Δ CI
excludes 0 (§5z); otherwise keep centralization-only. Record driving sequence edges
in `reflex.evidence`. (Blocked until iter-3 TRP completes and iter-4 TRP starts.)

## Rules (preserved for reference)

- No test-specific patches. Act only on signal general across ≥2 problems.
- Metadata iterations (#1, #2, #5) are no-regression guards, not improvement measurements.
- Only #4 can move the pass rate.
- §5z gate: 95% CI of per-seed Δ excludes 0, ≥3 seeds.
- Atomic commits. TRP ran; RIP snapshot in `KB_BASELINE.md` before next iter.
