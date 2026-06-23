# Pre-registration — MU_BUILD_ORDER A/B (plan Step 0.6 / S6 proof obligation)

Written **before** the run (I6). Capability: bottom-up build order — `plan.reorder_plan`
(callee/manifests first, tests last) + incremental Makefile (`make check` woven per
slice) + ledger gate-dedup (no double-build). Flag `MU_BUILD_ORDER=1`; off = baseline.

**Model:** `qwen2.5-coder-7b-instruct`, ctx 6000, fresh plan each run, unseeded.

**Arms (N=15 each):** for each problem, `MU_BUILD_ORDER=1` (ON) vs unset (OFF):
- **Acts (multi-file, build-order reorders + weaves):** p2-sqlite (py: model+app+test),
  p3-sdl2 (C: source + Makefile).
- **Control (single-file ⇒ reorder is a near-no-op, must not regress):** p1-helloworld.
- Excluded to keep the run fast & clean: p7/p8/p9 (heavy pip/npm installs — a smoke
  run showed a hallucinated `spacy` dep hitting a 120 s pip timeout, which is model
  noise equal across arms but slow/flaky); p10 (staged, currently 0/15 on backend —
  measured separately). Expand the set in a follow-up if this first A/B shows signal.

**Statistic:** Δ = ON − OFF. Per-problem Beta-Binomial posterior-difference sampling
(stdlib), summed for the set objective.

**KEEP gate (pre-registered):**
1. **P1:** ΔE[#solved] = Σ_i (pass_rate_ON − pass_rate_OFF), 95% CI lower bound **> 0**.
2. **P2:** every problem's Δpass-rate not a regression (point Δ ≥ −0.05 ∧ no proven
   harm; underpowered strict CI reported), especially the p1 control.

KEEP (P1∧P2) ⇒ `MU_BUILD_ORDER` on by default. Else ⇒ stays opt-in.

**Secondary (reported, not gated — where build-order plausibly helps even if pass-rate
is flat, §2.3 cost axis):** Δ avg repair-iters (gate-dedup + cascade-control ⇒ fewer),
Δ stochasticity. A null pass-rate effect with a real repair-iters/cost reduction and no
regression is itself a finding (efficiency KEEP candidate).

**Prior/expectation (honest):** these problems mostly pass on 7b already; build-order's
likely effect is **efficiency** (fewer redundant gate runs) more than pass-rate. The
cascade-control pass-rate payoff is expected on hard multi-layer goals (p10), which
can't show it until p10's backend builds (see S2 ablation lesson).
