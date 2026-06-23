# Pre-registration — S2 RE-EVALUATION (post-MSB1003-fix) · plan Step 0.3

Written **before** the run (I6). S2's first ablation (2026-06-22, `.mu/abl_s2_verdict.md`)
verdicted DROP→opt-in because p10 was **0/15 on every layer with S2 on AND off** — but
the MSB1003 A/B (2026-06-23, `.mu/abl_msb_verdict.md`) showed that was a **masking
artifact**: `dotnet test tests/` failed with MSB1003 *before* compilation, so CS0101
(S2's target) never arose. With the MSB1003 fix shipped (commit `8f82b34`, default-on),
`dotnet test` now reaches compilation and **CS0101 is the first error in 6/15** ON-arm
runs. This re-ablation asks: **does S2 now lift backend_build?**

**Single variable.** Toggle only S2 (`MU_S2_TYPE_REFLEXES=1` = ON, unset = OFF). All
else at shipped default — crucially `MU_ASPNET_ENTRYPOINT` **unset** (the entry-point
lever is separately unproven; confounding the two would make neither interpretable).

**Model:** `qwen2.5-coder-7b-instruct`, ctx 6000, fresh plan each run, unseeded.

**Arms (N=15):**
- **Headline — p10-dotnet-vue-blog** (staged; per-layer q̂). S2 fires in
  `_inter_stage_gate`, the staged path p10 uses.
- **Control — p4-fibonacci** (`dotnet`, single-`run`; S2 never fires there ⇒ ON≡OFF, a
  pure no-regression check).

**Statistic:** Δ = ON − OFF, Beta-Binomial posterior-difference, 60k draws.

**KEEP gate (pre-registered):**
1. **P1:** p10 `backend_build` Δq̂ (ON−OFF) 95% CI lower bound **> 0** ⇒ S2 on by default.
2. **P2:** p4 Δpass-rate no regression (point Δ ≥ −0.05 ∧ no proven harm).

**Honest expectation:** S2 can only rescue the ~6/15 CS0101-first runs; the other ~6/15
still bind on CS0246 (no `Program` entry — entry-point lever held off), capping any
lift. So a *partial* backend_build rise is plausible but P1 (CI lo > 0) may still fail
if CS0246 dominates. Either way the result is informative: a positive Δ says "ship S2 +
build the entry-point lever"; a null says "CS0246 is the true binder — entry-point lever
first, S2 after." Secondary (reported): p10 p_solve, pass_rate, repair-iters; the ON-arm
first-error mix (is CS0101 gone, leaving CS0246?).
