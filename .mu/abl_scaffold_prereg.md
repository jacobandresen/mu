# Pre-registration — SCAFFOLD lever A/B · scaffolding.md §5

Written **before** the run (I6). Closes the last open box of `docs/plans/scaffolding.md`
§7. Sister experiment to the TFM-grounding A/B (`abl_tfm_prereg.md`): both attack the same
p10 **restore wall** — scaffolding from the *prevent* side (the project never authors the
failing csproj), TFM-grounding from the *repair* side. They are **substitutes, measured
against each other (Arm 3), never stacked.**

**Why this lever.** Archive scan (2026-06-24): **59/61** recent p10 runs die at NuGet
**restore** (NU1202 / NETSDK1226) before any code compiles, because the *model* authors a
`net5.0`+EF8 csproj against a .NET-10-only SDK. Scaffolding runs `dotnet new webapi` at the
top of the backend stage and owns the csproj, so the failing file is never authored. D1
adds `AllowMissingPrunePackageData` (NETSDK1226 trigger on SDK ≥ 9); D2 `dotnet add package`
adds EF when the goal signals it. Verified zero-LLM on this host (.NET 10.0.109): bare
`dotnet new webapi` fails restore (NETSDK1226), restores in 1.1s after D1; D2 resolves EF to
the SDK major (10.0.9) and restores in 0.9s. **This A/B asks: does that prevent-side lift
backend_build under the live model?**

**Single variable.** Toggle only `MU_SCAFFOLD` (=1 ON with
`MU_SCAFFOLD_STACKS=dotnet-webapi,dotnet-xunit`, unset OFF). All else at shipped default —
`MU_TFM_GROUNDING`, `MU_ASPNET_ENTRYPOINT`, `MU_S2_TYPE_REFLEXES` held **unset** (the first
proven null/parked, the latter two confounders); the orchestrator `unset`s them so no shell
leakage confounds an arm. OFF is byte-identical (`scaffold()` early-returns when MU_SCAFFOLD
≠ '1'). Arm 3 instead sets `MU_TFM_GROUNDING=1` with `MU_SCAFFOLD` unset.

**Model:** `qwen2.5-coder-7b-instruct`, ctx 6000 (qwen sweet spot, MODELS.md — matches every
prior ablation for comparability; 12288 from `~/.zshrc.mu` was ~3× slower at no measured
benefit), fresh plan each run, unseeded
(`mu dojo measure` spawns a fresh `mu agent` subprocess per run).

**Arms (N=15 each):**
- **Headline — p10-dotnet-vue-blog** SCAFFOLD ON vs OFF (staged; per-layer q̂). The recipe
  fires on the .NET stage where the §0 cascade lives — for p10 the architect files the EF/
  SQLite project under the **model** stage (its "data layer"), so dotnet recipes are eligible
  in model+backend; only the frontend stage is JS-only (`dotnet-webapi` precedence).
- **Arm 3 (prevent vs repair) — p10** SCAFFOLD ON vs `MU_TFM_GROUNDING=1`. Same wall, two
  remedies; which clears restore more reliably. Reuses the SCAFFOLD-ON arm; adds a TFM-ON arm.
- **Control — p4-fibonacci** SCAFFOLD ON vs OFF (`dotnet`, recipe-eligible as `dotnet-xunit`,
  but a single-project test goal — scaffolding must not regress it).
- **Controls — p1-helloworld, p2-sqlite** SCAFFOLD ON vs OFF (non-dotnet; the recipe must
  **never fire** — `meta.json.scaffold` must be null on every run).

**Statistic:** Δ = ON − OFF, Beta-Binomial posterior-difference (matching
`observe.beta_binomial`, 60k draws) — same machinery as `abl_tfm_analyze.py`.

**KEEP gate (pre-registered):**
1. **P1 (headline):** p10 `backend_build` Δq̂ (ON−OFF) 95% CI lower bound **> 0** ⇒ flip
   `MU_SCAFFOLD` on by default (+ default `MU_SCAFFOLD_STACKS`), record efficacy Δ.
2. **P2 (controls):** p4/p1/p2 no regression — point Δ ≥ −0.05 ∧ no proven harm (CI hi ≥
   −0.05); p1/p2 additionally require `scaffold`==null on every run (recipe never fired).

**Mechanistic secondary (reported, not gated):** does **NU1202/NETSDK1226 drop out of the
ON-arm `backend_build` first-error mix** (the zero-LLM `nu1202_diagnosis.md` scan)? This is
the direct test of the §0 thesis — proves the recipe fired and cleared the wall, independent
of whether the now-reachable downstream binder (CS0246/CS0101) lets the gate clear.

**Honest expectation.** Scaffolding should clear restore reliably (proven zero-LLM), so
NU1202/NETSDK1226 should largely vanish from the ON arm. But clearing the wall exposes the
next binder (CS0246 entry-point, CS0101 dup types) — both currently PARKED levers. So P1
may still miss CI-lo>0 if compilation immediately re-binds. Either way it is informative: a
positive Δ says "ship it"; a null with the wall cleared says "re-run entry-point + S2 with
restore reachable" (scaffolding.md §5 close). N=15/arm single-problem CI ≈ ±0.165, so read a
null P1 as **inconclusive**, not harmful. Arm 3 tells us whether to ship prevent or repair.

**Level:** L2 (scaffolded) recorded in `meta.json.minimize`/`scaffold` (I3) — never compared
across rungs with the L0 baseline silently.

---
**Execution note (2026-06-25):** run **headline-only** first (`HEADLINE=1` ⇒ p10 SCAFFOLD
on/off, N=15) — each p10 run is slow (architect 480s + 3 staged build/test/repair loops on
360s budgets), so the full 9-arm sweep is ~8–12 h. P1 (the default-on decision) is decided by
the headline pair; the p4/p1/p2 controls and Arm 3 (vs TFM) are deferred and must run before
the default is actually flipped (the analyzer reports **PROVISIONAL KEEP** until then). ctx
lowered 12288→6000 after observing ~3× slowdown at no benefit (the smoke run already proved
the mechanism: scaffold fires, NU1202/NETSDK1226 clear, CS0246 next).
