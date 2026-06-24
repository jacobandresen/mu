# Ablation log — levers tried, results, and verdicts

The canonical record of every behaviour lever we have A/B-tested against the dojo, what
it measured, and whether it earned its place. **Read this before proposing or re-running
a lever** — most "obvious" ideas here have already been tried.

The raw experiment artifacts (prereg, orchestrator, analyzer, per-arm JSON, verdict)
live under the gitignored `.mu/` scratch (`abl_*`), which does **not** travel with the
repo. This file is the durable distillation of those verdicts.

## Method (so the numbers below are legible)

- **Board:** `mu dojo measure <problem> -n N`, single-variable on/off, fresh process per
  run. Headline problem **p10-dotnet-vue-blog** (the one 0-pass problem, q̂≈0.14);
  p1/p2/p4 act as controls.
- **Per-layer q̂:** fraction of runs that *clear* each layer (backend_build, backend_test,
  frontend_build, frontend_test). The gate layer is **backend_build**.
- **Pre-registered decision rubric** (see `docs/plans/p10-minimization.md` §2.3 / §4.1):
  - **P1 (headline):** p10 backend_build Δq̂ 95%-CI lower bound **> 0** ⇒ flip default-on.
  - **P2 (control):** no control problem regresses (point Δ ≥ −0.05 ∧ no proven harm).
  - N=15/arm is underpowered: a single-problem CI is roughly ±0.165, so a true null
    reads as "CI lo ≈ −0.166, FAIL P1." Read null P1s as *inconclusive*, not *harmful*.

## Status taxonomy

| Status | Meaning |
|---|---|
| **SHIPPED** | Default-on. Either proved lift or is a no-regret mechanical fix. |
| **UNDER TEST** | Default-off, gated; A/B in progress or queued. Do not cull. |
| **PARKED** | Default-off, gated. Null/inconclusive *behind a known upstream wall* — kept for re-test once the wall clears, not condemned. |
| **DROPPED** | Tried and deemed not worth keeping. Cull candidate. |

## Summary

| Lever | Flag | Hypothesis | p10 backend_build result | Verdict |
|---|---|---|---|---|
| MSB1003 `dotnet test <dir>` redirect | (always on) | empty `tests/` dir MSB1003s before compile | MSB1003 **10/15 → 0/15**; gate still 0/15 (moved deeper) | **SHIPPED** (no-regret) |
| TFM grounding | `MU_TFM_GROUNDING` | model's `net5.0` csproj fails NuGet restore (NU1202) before compile | — (A/B un-run) | **UNDER TEST** |
| ASP.NET entry-point task | `MU_ASPNET_ENTRYPOINT` | architect never plans `Program.cs` ⇒ CS0246 | 0/15 ON = 0/15 OFF (Δ≈0, behind NU1202 wall) | **PARKED** |
| S2 cross-stage type reflexes | `MU_S2_TYPE_REFLEXES` | duplicate/missing types across stages ⇒ CS0101/CS0246 | 0/15 ON = 0/15 OFF (Δ≈0, behind NU1202 wall) | **PARKED** |
| Build-order weave | `MU_BUILD_ORDER` | building deps before dependents cuts repair iters | n/a (tested on p1/p2/p3) — no pass-rate lift | **PARKED** |

## The meta-result that reframes the PARKED rows (NU1202 wall)

`.mu/nu1202_diagnosis.md` (zero-LLM, mechanical): **59/61 recent p10 archives die at
NuGet restore, before compilation ever runs.** The model authors its own `.csproj` with
`<TargetFramework>net5.0</TargetFramework>` plus `EntityFrameworkCore 8.0.0` (needs
net8.0+); the installed SDK is .NET 10 only, so restore fails with **NU1202** and the
compiler never sees the code.

Consequence: **entry-point and S2 act *downstream* of a wall ~97% of runs never clear.**
Their 0/15 = 0/15 verdicts are real but *uninformative about the levers themselves* —
neither could fire. That is why they are **PARKED, not DROPPED**: the honest next step is
to re-test them once `MU_TFM_GROUNDING` clears restore and compilation (CS0246/CS0101)
finally becomes reachable. Empirically, bumping the TFM net5.0→net8.0 clears restore;
→net10.0 + `AllowMissingPrunePackageData` reaches real compilation.

## Per-lever detail

### MSB1003 redirect — SHIPPED (no-regret)
`8f82b34`. `normalize_test_command`'s `dotnet test <dir>` redirect was guarded on
`arg_path.is_dir()` and ran at grounding time, before `tests/` existed, so it no-oped.
Fixed to fire whenever `<dir>` resolves to no `.csproj`. A/B (`abl_msb`): MSB1003
eliminated **10/15 → 0/15**; every run now reaches restore/compile. backend_build still
0/15 — the bottleneck *moved deeper* (to NU1202, then CS0246/CS0101). p4 control PASS
(+0.06). Kept because it is a strictly-correct mechanical fix with no observed harm.

### ASP.NET entry-point task (`MU_ASPNET_ENTRYPOINT`) — PARKED
`13a81cd`. CS0246 root cause: the architect plans Models/DbContext/Controllers but no
entry point, so `Program` doesn't exist and `WebApplicationFactory<Program>` can't
compile. `ground_plan` injects a `Program.cs` *task* (writer authors it — no
pregenerated code). A/B (`abl_ep`): p10 0/15 = 0/15 (Δ≈0). p4 control read 5/15 vs 8/15
(Δ −0.18) → recorded **REVERT**. **Caveat:** the gate is guarded on `needs_ef` and
should not fire on p4 at all, so that "regression" is almost certainly stochastic — the
later S2b run saw p4 swing the *opposite* way (9/15 vs 3/15) on a lever that also never
fires on p4, confirming p4 single-run pass-rate is just noise at N=15. Kept opt-in,
queued for re-test post-TFM.

### S2 cross-stage type reflexes (`MU_S2_TYPE_REFLEXES`) — PARKED
First ablation (`abl_s2`, `f77a748`): p10 0/15=0/15 → **DROP to default-off**. Re-eval
after the MSB1003 fix (`abl_s2b`): still 0/15=0/15 — **STAYS OPT-IN**; CS0246 (no
`Program`) binds the runs S2 can't touch. p4 control PASS but pure noise (S2 never fires
single-run). Default-off; re-test once entry-point + TFM make CS0101/CS0246 reachable.

### Build-order weave (`MU_BUILD_ORDER`) — PARKED
`abl_bo`, plan S6. Tested on p1/p2/p3 (p10 doesn't build yet): ΔE[#solved] +0.06, CI
[−0.26, +0.38] → **P1 FAIL, no pass-rate lift on easy problems** (expected — they rarely
need ordering). P2 PASS (no regression). Default-off; the value (if any) is in repair-iter
efficiency on hard multi-layer goals — re-test once p10 builds.

### TFM grounding (`MU_TFM_GROUNDING`) — UNDER TEST
`4d7757f`+`743c8bc`. Reflex `fix_csharp_uninstalled_tfm`: when a model-authored csproj's
`<TargetFramework>` major is below the installed SDK and a Microsoft.*/EntityFrameworkCore
package major exceeds it, raise the TFM to the installed SDK and add
`AllowMissingPrunePackageData` for net9+. Directly targets the NU1202 wall above. Prereg
`abl_tfm_prereg.md`; A/B harness `abl_tfm_run.sh`/`_analyze.py` ready but **un-run**
(launched 2026-06-24, stopped before any arm finalized). Gates: P1 p10 backend_build
Δq̂ CI-lo>0 ⇒ flip default-on; P2 p4 control; mechanistic secondary — did NU1202 drop
out of the ON-arm first-error mix? **This is the lever that, if it lands, unblocks
re-testing the two PARKED levers above.**

## Observed failure modes (the evidence levers are aimed at)
From archive scans (`.mu/round2-7_scan.md`, ~390 sessions) and `nu1202_diagnosis.md`.
The recurring p10 backend_build first-errors, in the order the levers peel them back:
**MSB1003** (no project) → **NU1202** (restore / wrong TFM) → **CS0246** (no `Program`
entry) / **CS0101** (duplicate types across stages) → model syntax errors (CS1026 etc.).
Each documented in `docs/challenges/`.

## How to add a row
1. Pre-register in `.mu/abl_<tag>_prereg.md` (hypothesis, flag, gates, N) **before** running.
2. Run the on/off A/B; let `abl_<tag>_analyze.py` write `.mu/abl_<tag>_verdict.md`.
3. Distil the verdict into the Summary table + a Per-lever entry here, and set the status.
   SHIPPED ⇒ flip the default and note the commit; DROPPED ⇒ cull the code in the same PR.
