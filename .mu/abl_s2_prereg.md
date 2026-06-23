# Pre-registration — S2 cross-stage type-reflex ablation (plan Step 0.3 KEEP gate)

Written **before** the run (I6). Plan: `docs/plans/p10-minimization.md` §4.3 Step 0.3.

**Model:** `qwen2.5-coder-7b-instruct` (the sweep winner, 7/10; p10 0/5, bottleneck
backend_build q̂=0.14 on the L0 7b board). ctx 6000. Fresh plan each run, unseeded.

**Reflexes under test (S2):**
- `fix_csharp_cross_stage_duplicate_types` (CS0101)
- `fix_csharp_public_signature_accessibility` (CS0053)

**Arms (N=15 each, the §2.3/§4.5 power):**
| arm | problem | S2 | emit |
|---|---|---|---|
| p10 ON  | p10-dotnet-vue-blog | enabled (default) | `.mu/abl_p10_s2on.json` |
| p10 OFF | p10-dotnet-vue-blog | `--disable` both  | `.mu/abl_p10_s2off.json` |
| p4 ON   | p4 (control/coverage) | enabled | `.mu/abl_p4_s2on.json` |
| p4 OFF  | p4 | `--disable` both | `.mu/abl_p4_s2off.json` |

**Statistic:** Δ = (ON − OFF). 95% CI by Beta-Binomial posterior-difference sampling
(`observe.beta_binomial` priors, stdlib draws).

**KEEP gate (pre-registered):**
1. **Headline (decisive):** p10 **backend_build q̂** Δ CI lower bound **> 0** — the
   continuous metric the plan powers at N=15 (§4.5, Result 3).
2. **Control (safety, p4):** no regression — point Δ ≥ −0.05 **and** no demonstrated
   harm (difference CI not entirely below −0.05).

**Power note (pre-registered, not post-hoc):** the strict §4.1 form "difference-CI
lower bound ≥ −0.05" is *unachievable* for a binary per-problem pass-rate at N=15 —
the difference-of-binomials CI is ~±0.28, so it fails even at Δ=0. Per §4.5 binary
pass-rate needs N≈50; the headline therefore gates on continuous q̂, and the control
vetoes only on **demonstrated** harm. The strict bound is still reported for
transparency.

KEEP (1 ∧ 2) ⇒ S2 stays on by default. Else ⇒ disabled-by-default behind the
ablation flag (the reflex is retained, just not auto-applied). Secondary (reported,
not gated): p10 p_solve, all four layer q̂, repair-iters, stochasticity.
