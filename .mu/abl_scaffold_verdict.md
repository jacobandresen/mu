# SCAFFOLD lever A/B — scaffolding.md §5 backend_build

model `qwen2.5-coder-7b-instruct` · level L2 (I3) · ON = MU_SCAFFOLD=1 (dotnet-webapi,dotnet-xunit) · OFF = unset · entry-point + S2 + TFM held off


## p10-dotnet-vue-blog — per-layer q̂ (ON = scaffolded backend)

| layer | ON clears | OFF clears | Δq̂ (ON−OFF) | 95% CI |
|---|---|---|---|---|
| backend_build **←gate** | 0/15 | 0/15 | -0.001 | [-0.166, +0.164] |
| backend_test | 0/15 | 0/15 | -0.000 | [-0.164, +0.165] |
| frontend_build | 0/15 | 0/15 | -0.000 | [-0.166, +0.162] |
| frontend_test | 0/15 | 0/15 | -0.001 | [-0.166, +0.166] |

p_solve: ON 0.0 vs OFF 0.0 · pass-rate ON 0.00 vs OFF 0.00 · repair-iters ON 4.0 vs OFF 6.0

## p4-fibonacci (dotnet control) — INCOMPLETE (arm JSON missing)

## p1-helloworld (non-dotnet control) — INCOMPLETE (arm JSON missing)

## p2-sqlite (non-dotnet control) — INCOMPLETE (arm JSON missing)

## Verdict

- Gate 1 (p10 backend_build Δq̂ CI lo > 0): FAIL (lo=-0.166)
- Gate 2 (controls p4/p1/p2): **not evaluated** (headline-only run)

**INCONCLUSIVE at N=15 (P1 CI-lo ≤ 0). Check the mechanistic secondary (did NU1202/NETSDK1226 drop from the ON arm?): if restore cleared but compilation re-binds on CS0246/CS0101, re-run entry-point + S2 with the wall now reachable (scaffolding.md §5).**

## Mechanistic secondary — the restore wall (the §0 thesis)

Zero-LLM scan of the 30 archived p10 sessions, split by `meta.json.scaffold`:

| arm | scaffold fired | NU1202/NETSDK1226 present | downstream error mix |
|---|---|---|---|
| ON  | 15/15 (`dotnet-webapi`) | **0/15** | CS7022·3, CS0246·3, CS8618·3, CS1002/1026/1519/1513 (syntax), CS1061, CS0051, CS0101·1 |
| OFF | 0/15 (`null`) | **12/15** | NU1202·12, CS0246·2 |

**The wall is cleared.** Scaffolding eliminated NU1202/NETSDK1226 (12/15 → 0/15) and every
ON run reached real compilation; the binder moved downstream to *model-authored* code
(entry-point/type/nullable/syntax errors). This confirms the §0 thesis directly: the restore
wall that masked 97% of backend_build runs is a structural problem scaffolding removes by
construction. backend_build stays 0/15 because qwen-7b cannot author a clean compiling
ASP.NET+EF backend even with the project laid down (the model ceiling, now exposed).

**Follow-up (D3):** CS7022 (multiple entry points) appears 3× in ON — the scaffold's
`dotnet new` `Program.cs` (top-level statements) coexisting with the model's own entry point.
The scaffold leaves `Program.cs` model-owned (D3); the model adds a second entry point rather
than editing the host. Worth a reflex or a sharper D3 (own/skeleton `Program.cs`) when the
PARKED entry-point lever is re-tested with scaffolding ON.

**Disposition:** STAYS OPT-IN (`MU_SCAFFOLD`, default off) — no headline lift at N=15, but the
prevent side is proven to clear the wall. Next: re-run the entry-point + S2 A/Bs with
`MU_SCAFFOLD=1` (compilation now reachable), and run the deferred p4/p1/p2 controls before any
default flip. Arm 3 (vs `MU_TFM_GROUNDING`) still open.
