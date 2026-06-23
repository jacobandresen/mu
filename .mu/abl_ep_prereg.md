# Pre-registration — ASP.NET ENTRY-POINT lever A/B · plan Step 0.4

Written **before** the run (I6). Top pending item from the machine-move handoff
(`docs/handoff/MACHINE_MOVE.md`): the entry-point lever shipped UNPROVEN (`13a81cd`,
flag `MU_ASPNET_ENTRYPOINT`, default off). The MSB1003 A/B moved the p10 `backend_build`
bottleneck deeper to **CS0246 ×6 + CS0101 ×6** (archive scan 2026-06-23). CS0246 is the
dominant first-error and is **upstream** of CS0101: the architect plans
Models/DbContext/Controllers but never an entry point, so `Program` doesn't exist and
`WebApplicationFactory<Program>` cannot compile. `ground_plan` now injects a `Program.cs`
*task* (writer authors it — no pregenerated code, §0.2) when `MU_ASPNET_ENTRYPOINT=1`.
This A/B asks: **does the entry-point lever lift backend_build?**

**Single variable.** Toggle only `MU_ASPNET_ENTRYPOINT` (=1 ON, unset OFF). All else at
shipped default — crucially `MU_S2_TYPE_REFLEXES` **unset** (the S2 re-eval is a
separate, later ablation; confounding the two would make neither interpretable). The
orchestrator `unset`s S2 explicitly so no shell leakage confounds the arm.

**Model:** `qwen2.5-coder-7b-instruct`, ctx 6000, fresh plan each run, unseeded.

**Arms (N=15):**
- **Headline — p10-dotnet-vue-blog** (staged; per-layer q̂). The lever fires in
  `ground_plan` on the EF-ASP.NET path p10 uses.
- **Control — p4-fibonacci** (`dotnet`, no EF). The gate is narrowly guarded on
  `needs_ef`, so it cannot fire here ⇒ ON≡OFF, a pure no-regression check.

**Statistic:** Δ = ON − OFF, Beta-Binomial posterior-difference (matching
`observe.beta_binomial` prior), 60k draws — same machinery as `abl_msb_analyze.py` /
`abl_s2b_analyze.py`.

**KEEP gate (pre-registered):**
1. **P1 (headline):** p10 `backend_build` Δq̂ (ON−OFF) 95% CI lower bound **> 0** ⇒
   flip `MU_ASPNET_ENTRYPOINT` on by default, record efficacy Δ.
2. **P2 (control):** p4 Δpass-rate no regression — point Δ ≥ −0.05 ∧ no proven harm
   (CI hi ≥ −0.05); strict §4.1 CI-lo reported but underpowered at N=15 (§4.5).

**Mechanistic secondary (reported, not gated):** does the injected `Program.cs` task
appear in the ON-arm plans, and does **CS0246 drop** from the ON-arm `backend_build`
first-error mix? (The analogue of MSB's "MSB1003 disappears" check — proves the lever
fired, independent of whether it cleared the gate.)

**Honest expectation:** CS0246 is upstream and dominant (~6/15), so the lever is the
likely *bigger* `backend_build` mover than S2 — but CS0101 (~6/15, S2's target, held
off here) may immediately re-bind once `Program` exists, capping the lift below CI-lo>0.
Either way it is informative: a positive Δ says "ship the lever, then re-test S2 with it
on"; a null with CS0246 gone says "CS0101 is now the binder ⇒ S2 next". p4 flat.
Secondary: p10 p_solve, pass_rate, repair-iters.
