# Plan: Iteratively implement the Reflex KB

Five iterations on `kb-implementation`. Claude implements, local model
(`qwen2.5-coder-7b-instruct`, `MU_NUM_CTX=6000`) provides feedback.
One iteration per turn; TRP + RIP mandatory between each.

**Rules:** No test-specific patches. Act only on signal general across ≥2 problems.
Metadata iterations (#1, #2, #5) are no-regression guards, not improvement
measurements. Only #4 can move the pass rate.

**Loop per turn:**
implement → `pytest tests/ -q` + `mu kb` → TRP → RIP → commit → stop.

**TRP:**
```sh
ROUNDS=5 MU_NUM_CTX=6000 MU_AGENT_MODEL=qwen2.5-coder-7b-instruct \
  python3 -m mu.dojo practice --rounds 5
```

**RIP checklist:**
1. Pass rate / repair-iters / tokens/call vs prior snapshot? (`repair-iters` ↑ = regression even if pass rate holds)
2. Skim `CHALLENGES.md ## Open` + `dojo-failures.md` root causes
3. `python -m mu.observe` — top signature ≥5 occurrences + deterministically fixable → next candidate
4. Propose: tune shipped item / add reflex (≥2 problems, §5z gate) / move on
5. Record dated snapshot in `KB_BASELINE.md`, commit, hand back

---

## Status

| # | Iteration | Status | Commit |
|---|---|---|---|
| 0 | Baseline snapshot | ✓ | 8ff56e9 |
| 1 | Idempotency test harness | ✓ | a6798d3 |
| 2 | Schema fields + efficacy storage | ✓ | 53d6e06 |
| 3 | Shared-core refactor | ✓ | — |
| 4 | Offline-baked chain order | pending | — |
| 5 | Validation discipline + interaction model | pending | — |

---

## Iteration 3 — Shared-core refactor (§5), behavior-preserving

Extract generic core + thin `(parser, predicate)` adapters for the "one algorithm +
per-toolchain table" families:
- Start with **duplicate-declaration** (`fix_rust_duplicate_use`,
  `fix_js_duplicate_require`, `fix_csharp_duplicate_classes`). Iter-1 idempotency
  + frozen-output tests are the golden gate — byte-identical output before/after.
  Keep public `fix_*` names as thin wrappers (registry + `agent.py` call sites).
- Repeat per family only if the first lands clean.
- **TRP → RIP.** Strict no-regression: any metric Δ is a bug. Also
  `mu dojo measure --seed 42` A/B on an affected problem.

---

## Iteration 4 — Offline-baked chain order (§8) — the only real lever

No central chain: `run_reflexes` takes whatever the caller passes; orders live
per-language and in scattered `agent.py` call sites (`:814`, `:1309`,
`apply_*_reflexes`). Two parts:

1. **Centralize** into a registry-derived ordered list — behavior-preserving under
   iter-1 tests.
2. **Bake an order** offline from §7/§8 sequence edges + posteriors as a static
   constant (never online sampling — preserves `MU_SEED` determinism).

**TRP → RIP.** `mu dojo measure --seed` A/B across ≥3 seeds. Keep new order only
if Δ CI excludes 0 (§5z); otherwise revert order, keep centralization. Record
driving sequence edges in `reflex.evidence`.

---

## Iteration 5 — Validation discipline + interaction model (§11 / §8 / §2)

- `tests/test_calibration.py`: simulate Bernoulli rates, assert Beta-Binomial
  achieves ~95% coverage.
- `tests/test_ablation_rule.py`: reusable §5z predicate (reuses `sz5_gate()`).
- **Honesty audit**: flag reflexes whose firings concentrate on a single problem
  (AGENTS §0/§2) — observational warning in `mu kb report()`.
- **Interaction model** (`pgmpy` optional, lazy import): Bayesian net over
  co-occurrence + sequence data in `firing`. Strictly observational/offline —
  never feeds the runtime runner or `predict.py` (§10 leak guard).
- **TRP → RIP (final).** Run audit. Update README + flip `REFLEX_KB.md`
  planned → built.

---

## Verification (per iteration)

- `pytest tests/ -q` + `mu check` green; `mu kb` rebuilds.
- TRP ran; RIP snapshot in `KB_BASELINE.md` before next iteration starts.
- For #3/#4: `mu dojo measure --seed 42` A/B (≥3 seeds where Δ claimed).
- Atomic commit, `Co-Authored-By: Claude`.

## Risks

- **#4 is the risky one** — centralizing scattered call sites can change behavior;
  iter-1 tests are the gate; revertible (keep centralization if order shows no Δ).
- **Metadata runs measure noise** — never claim pass-rate gain from N=5.
- **Lucky signature** — §5z gate + ≥2-problem threshold before any reflex
  added/kept.
