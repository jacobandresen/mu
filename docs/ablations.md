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
- **Pre-registered decision rubric:**
  - **P1 (headline):** p10 backend_build Δq̂ 95%-CI lower bound **> 0** ⇒ flip default-on.
  - **P2 (control):** no control problem regresses (point Δ ≥ −0.05 ∧ no proven harm).
  - N=15/arm is underpowered: a single-problem CI is roughly ±0.165, so a true null
    reads as "CI lo ≈ −0.166, FAIL P1." Read null P1s as *inconclusive*, not *harmful*.
- **Why these levers, ranked.** A lever's value is its expected gain in
  `E[N_solved] = Σ_i P_i` over the *whole set*, ∝ logistic headroom `q(1−q)` × the chain
  factor `∏_{ℓ′≠ℓ} q_{ℓ′}`. p10 sits at q≈0 on every layer (both factors ≈0), so broad
  no-regret levers and the steep mid-tier problems outrank dragging p10 — and the .NET ladder
  is model-ceiling-bound (see the p13 validation below). This is the rationale the now-removed
  `p10-minimization.md` plan carried; the operative facts live here and in [DOJO.md](../DOJO.md)
  (Problem-space minimization).

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
| Scaffold (`dotnet new`) | `MU_SCAFFOLD` | model authors `net5.0`+EF8 csproj ⇒ NU1202/NETSDK1226 restore wall | NU1202/NETSDK1226 **12/15 → 0/15** (scaffold fired 15/15); gate still 0/15 (moved to CS0246 + model syntax errors); repair-iters 6.0→4.0 | **OPT-IN** — wall cleared (mechanistic win) but headline null at N=15; re-test PARKED entry-point + S2 now restore is reachable (`.mu/abl_scaffold_verdict.md`) |
| TFM grounding | `MU_TFM_GROUNDING` | model's `net5.0` csproj fails NuGet restore (NU1202) before compile | 0/15 ON, 0/8 OFF (partial); both arms identical — null Δ | **NULL — STAYS OPT-IN** (mechanistic secondary below) |
| Roslyn LSP (`MU_LSP=all`) | `MU_LSP=all` | CS0246 persists after scaffold+TFM wall cleared — Roslyn `source.addImport` fixes remaining missing usings | — (A/B un-run) | **UNDER TEST** |
| ASP.NET entry-point task | `MU_ASPNET_ENTRYPOINT` | architect never plans `Program.cs` ⇒ CS0246 | p10: 0/15 (behind NU1202 wall). **p13 with wall cleared (scaffold+TFM): cuts CS0246 12→6** | **OPT-IN — validated, insufficient alone** |
| S2 cross-stage type reflexes | `MU_S2_TYPE_REFLEXES` | duplicate/missing types across stages ⇒ CS0101/CS0246 | p10: 0/15 (behind NU1202 wall). **p13 with wall cleared: cuts CS0101 10→4** | **OPT-IN — validated, insufficient alone** |
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

### Ladder validation on p13 (2026-06-25, the wall finally cleared)

Re-tested on **p13-dotnet-minimalapi** (the simplest .NET ladder rung — minimal API + xUnit
`WebApplicationFactory`, *no DB needed*), dark N=8, stacking the levers. The model adds EF+net5.0
even here, so the wall appears; scaffold owns the *backend* csproj but the model's *test* csproj
keeps net5.0+EF, so scaffold and TFM-grounding are **complementary** (different csprojs), not
substitutes, in the multi-project layout.

| config | NU1202 | CS0101 (dup) | CS0246 | repair-iters | pass |
|---|---|---|---|---|---|
| baseline | 15 | — | — | 3.8 | 0/8 |
| +scaffold | test csproj only | — | 46 | 4.5 | 0/8 |
| +scaffold +TFM | **0** | 10 | 12 | 3.8 | 0/8 |
| +scaffold +TFM +S2 +entry-point | **0** | **4** | **6** | **2.2** | 0/8 |

**The levers work** — the restore wall clears (NU1202 15→0) and S2/entry-point cut their target
errors once reachable (CS0101 10→4, CS0246 12→6, repair-iters 3.8→2.2). But p13 stays **0/8**:
the residual is the **model semantic ceiling** (CS0103 undefined-name ×21, CS1929, CS0841) —
7B-class models write semantically broken C# even for a trivial API. **Conclusion: on the .NET stack the
binding constraint is the model, not structure.** The structural levers are necessary and now
*validated*, but insufficient for this model; they stay opt-in (no pass-rate lift to bank).

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

### TFM grounding (`MU_TFM_GROUNDING`) — NULL, STAYS OPT-IN
`4d7757f`+`743c8bc`. Reflex `fix_csharp_uninstalled_tfm`: when a model-authored csproj's
`<TargetFramework>` major is below the installed SDK and a Microsoft.*/EntityFrameworkCore
package major exceeds it, raise the TFM to the installed SDK and add
`AllowMissingPrunePackageData` for net9+. Directly targets the NU1202 wall above.

**A/B result (partial):** ON 0/15, OFF 0/8 partial (run interrupted); both arms all-stall,
Δ≈0. Mechanistic secondary: NU1202 still appears in ON-arm first_errors — the reflex fires
on the test csproj but the backend csproj (model-authored in the MVC stage) may keep a
bad TFM. **Stays OPT-IN** — no headline lift; the p13 validation (scaffold+TFM: NU1202 15→0)
shows it works in compound but not alone at this problem size.

### Roslyn LSP (`MU_LSP=all`) — UNDER TEST
Roslyn `Microsoft.CodeAnalysis.LanguageServer` (net10) fires after each `.cs` file write
when `MU_LSP=all` is set; applies `source.addImport` code actions that fix CS0246
(missing `using`) for any SDK or NuGet type — more general than the regex reflex, which
only finds project-internal types. ~30s settle per file. Prereg `abl_lsp_prereg.md`;
A/B harness `abl_lsp_run.sh`/`_analyze.py`. Hypothesis: in the scaffold+TFM compound
config (wall cleared, CS0246 reachable), Roslyn cuts the residual CS0246 count further
than the regex reflex alone — validated on p13 dark N=8 (CS0246 12→6 with EP, Roslyn
expected to cut deeper via SDK-type usings). Gate: p13 `backend_build` Δq̂ CI-lo > 0.

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
