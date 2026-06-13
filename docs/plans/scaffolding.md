# Plan: employ scaffolders at ground time

_Implementation + evaluation plan for [TOOLS.md](../../TOOLS.md) §6.1 — generate a
project skeleton from an official template before the writer runs, so the model fills
only the logic. Status: **proposed**, not implemented._

---

## 0. Objective & hypothesis

**Objective.** When a goal targets a scaffold-able stack (an xUnit .NET test project, a
Vite + Vitest Vue app, a Cargo binary, …), materialise the canonical project skeleton
from a template at ground time and mark those structural files done, leaving the model to
write only the source and tests.

**Hypothesis (pre-registered).** Scaffolding removes the *structural* failure classes by
construction:

- p10 / p4 → eliminates [csharp-aspnet-scaffolding](../challenges/csharp-aspnet-scaffolding.md)
  (CS0017 duplicate entry point, MSB1003 missing project, NU1202 TFM mismatch).
- p9 → eliminates the config half of [vue-vitest-jest-setup](../challenges/vue-vitest-jest-setup.md)
  (Vitest globals, vite config, missing `vue` dep).

**Predicted effect:** p10 pass rate 0 → >0; p4/p9 up; **p1/p2/p5/p6 unchanged** (control);
median repair-iters and tokens/run down on treated problems. If the data don't show this,
the change is dropped.

---

## 1. Non-negotiable principle: offline-first

> **mu must function fully offline. Online scaffolding is optional and must always
> degrade to the offline path — never a hard dependency.** (User constraint, 2026-06-13.)

This partitions the scaffolders:

| Scaffolder | Network? | Tier |
|---|---|---|
| `dotnet new xunit` / `webapi` | **No** — templates ship with the SDK | **offline** (default-eligible) |
| `cargo new` | **No** | **offline** |
| `npm create vite` / `create-vue` | **Yes** — fetches the template on first use | **online-only** (opt-in) |

Rules enforced throughout:

1. The **offline tier** may run whenever `MU_SCAFFOLD=1` and the toolchain is present.
2. The **online tier** runs only when `MU_SCAFFOLD_ONLINE=1` *and* a reachability probe
   passes; otherwise it is skipped silently.
3. **Every recipe degrades to baseline**: if scaffolding is disabled, unavailable, or
   fails, mu proceeds exactly as today (the model writes the structure itself). Scaffolding
   can only *add* a head start, never *block* a run.
4. For the online tier we additionally provide an **offline fallback**: a vendored minimal
   template committed under `dojo/scaffolds/<stack>/` so a Vite/Vitest skeleton is available
   air-gapped. `npm create vite` is then only a *freshness* convenience, never required.

---

## 2. Background & framing

This is the **L2 "scaffold" rung** of the minimization ladder already defined in
[DOJO.md](../../DOJO.md): *provide manifest/config as fixtures, measure the logic.* The
existing fixture mode (`dojo/fixtures/<id>/`, `fixtures.py`) commits a per-problem fixture
by hand; scaffolding is the **general** version — generate the fixture from a template at
runtime, keyed off the detected stack, not the problem id. That generality is what keeps
it honest (see §5).

Hook point: `ground_plan` (`src/mu/plan.py`) already rewrites a recoverable plan before
the writer loop; scaffolding is a new grounding step beside it.

---

## 3. Design

### 3.1 Stack detection (general, not problem-keyed)

A small detector maps the goal text + parsed plan (toolchains, named frameworks) to a
scaffold recipe:

- `.NET test project` ← plan toolchain `dotnet` **and** goal/plan mentions xUnit / `dotnet test`.
- `.NET web API` ← `dotnet` **and** ASP.NET / minimal API / EF Core.
- `Vite + Vitest (Vue/TS)` ← `node` **and** Vite **and** Vitest.
- `Cargo binary` ← `cargo` (already partly covered by mu's minimal-manifest regen).

Detection reads **capabilities named in the goal**, never an id. A synthetic goal
("write an xUnit test project that …") must trigger the same recipe as p4 — this is an
explicit honesty test (§5, §6).

### 3.2 Recipe table (declarative)

Each recipe is `{stack → (tier, command|vendored_path, produced_files, mark_done, source_files)}`:

| Stack | Tier | Action | Files marked **done** (scaffold owns) | Files left to the **model** |
|---|---|---|---|---|
| .NET xUnit | offline | `dotnet new xunit -o .` | `*.csproj`, test-host wiring | test `.cs`, source `.cs` |
| .NET webapi | offline | `dotnet new webapi -o .` | `*.csproj`, `Program.cs` host bootstrap | model + EF model, endpoints |
| Cargo bin | offline | `cargo init --bin` | `Cargo.toml` | `src/main.rs` |
| Vite+Vitest | online (+vendored fallback) | `npm create vite@latest . -- --template vue-ts` then add vitest config | `package.json`, `vite.config.ts`, `tsconfig.json` | `src/*.vue`, `src/*.test.ts` |

`mark_done` files are added to PLAN.md as completed tasks so the writer skips them; the
model still authors the logic/test files.

### 3.3 Reconciliation with PLAN.md

Conflict case: the template writes `Program.cs` (host bootstrap) but the plan also lists
`Program.cs` (the API). Resolution rules:

1. **Scaffold owns** manifest/config/entry-wiring (`*.csproj`, `vite.config`, `package.json`,
   `tsconfig`, `Cargo.toml`).
2. **Model owns** source and tests; if the template seeds a stub the plan also targets, keep
   the file as a *task* (not marked done) but leave the template's correct project wiring in
   place — the model overwrites the stub body, not the structure.
3. Record every scaffolded path in `meta.json` (`scaffold: {stack, files, tier}`) for audit
   and so the analysis can separate scaffolded passes from from-scratch passes.

### 3.4 Control flag surface

- `MU_SCAFFOLD=1` — master switch (default **off** for clean A/B; offline tier eligible).
- `MU_SCAFFOLD_ONLINE=1` — additionally allow the network tier (default off).
- `MU_SCAFFOLD_STACKS=dotnet-xunit,vite-vitest` — scope to specific recipes (for A/B).
- All off ⇒ behaviour byte-identical to today.

---

## 4. `mu setup` / `mu check` changes

`mu check` (read-only, offline):

- Report **scaffold readiness** per installed toolchain: `dotnet new list` contains
  `xunit`/`webapi`; `cargo` present; (online) note whether the Vite template is cached.
- Never fail `check` for a missing online template — report it as "online scaffolding
  unavailable (offline fallback in use)".

`mu setup` (interactive):

- New optional step **"pre-warm scaffold templates"**, shown only if the user opts into
  online scaffolding. It (a) verifies bundled `dotnet new` templates, and (b) runs
  `npm create vite` once into a temp dir to populate the npm cache, then vendors the
  minimal result into `dojo/scaffolds/vite-vitest/` so future runs are offline.
- The offline tier needs **no** setup beyond the toolchain already installed by `mu setup`
  (the `dotnet`/`cargo` templates ship with the SDK).
- Document the two env flags in the `mu setup` summary and [docs/MODELS.md](../MODELS.md)
  is unaffected; add a short "Scaffolding" note to [DOJO.md](../../DOJO.md).

---

## 5. Honesty safeguards (the central design risk)

A scaffolder that keys on a dojo problem measures the test author, not the agent
([AGENTS.md](../../AGENTS.md) §0). Enforced by:

1. **Detection on capabilities only** — recipes match named stacks/frameworks, never ids.
2. **A general-trigger test** (§6): a synthetic non-dojo xUnit goal must scaffold; a goal
   with no stack signal must not.
3. **Minimization level recorded.** A scaffolded pass is an **L2** result, not L0; the
   analysis and `problems-catalog.json` `minimize` field must reflect that a scaffolded
   95% is not an open-ended 95% (DOJO.md). We are *measuring the logic*, by design — that
   is the point, but it must be labelled so runs aren't compared across levels.

---

## 6. Test & evaluation plan (end-to-end)

Follows [AGENTS.md](../../AGENTS.md) §5z (measure continuous metrics, multiple runs, pin
RNG, decide by interval) and reuses the efficacy machinery used for the `fix_inline_recipe`
ablation (`observe.py` Beta-Binomial posteriors, `efficacy_run` rows, `sz5_gate`).

**Arms.** Baseline (`MU_SCAFFOLD=0`) vs Treatment (`MU_SCAFFOLD=1`, offline tier;
plus a separate Treatment-online for the Vite recipe).

**Problems.** Treated: **p4, p9, p10**. Control (must not regress): **p1, p2, p5, p6**.

**Metrics per problem per arm:** pass rate, first-try rate, median repair-iters,
median prompt+generated tokens/run, stochasticity (`1 − modal/N`).

**Phases:**

- **Phase 0 — baseline.** `mu dojo measure <id> --runs 15` for all 7 problems, scaffold
  off. Record to `efficacy_run`. (Fresh plan each run — captures planner variance.)
- **Phase 1 — implement** detector + offline recipes + ground hook behind `MU_SCAFFOLD`
  (default off). Unit tests:
  - detection fires on a synthetic generic xUnit/Vite goal and not on a no-stack goal;
  - reconciliation marks only config/manifest files done;
  - **offline guarantee**: with the network blocked and `MU_SCAFFOLD_ONLINE=0`, an xUnit
    goal still scaffolds (offline tier) and a Vite goal falls back to vendored template or
    skips to baseline — no network call, no crash;
  - idempotence (scaffolding an already-scaffolded dir is a no-op);
  - graceful degradation (recipe command failure ⇒ baseline path, run continues).
- **Phase 2 — `mu setup`/`check`** scaffold-readiness + optional pre-warm; vendor the Vite
  fallback. Verify `mu check` passes offline with online scaffolding unavailable.
- **Phase 3 — treatment.** Repeat Phase 0's measurements with `MU_SCAFFOLD=1` (offline);
  separately measure p9 with `MU_SCAFFOLD_ONLINE=1` to isolate the network tier's added value.
- **Phase 4 — analyse.** Per problem, Δ(treatment − baseline) with 95% Beta-Binomial CI
  (`observe.Posterior`); apply the `sz5_gate`. Continuous metrics (iters, tokens) corroborate
  with far less noise than pass/fail (§5z).

**Pre-registered success criteria (KEEP):**

- p10 pass-rate CI **lower bound > 0** (currently a hard 0/12) — the headline.
- p4 and p9 pass-rate Δ positive with CI excluding 0, **or** a clear drop in median
  repair-iters/tokens even if pass/fail is noisy.
- **No control regression**: p1/p2/p5/p6 Δ CI must include 0 (and lower bound not below a
  small −ε margin).
- Treated problems show fewer repair-iters and lower tokens/run (the scaffold should make
  runs cheaper as well as more reliable).

**Drop criteria:** p10 unchanged, or any control problem regresses beyond −ε, or the online
tier adds nothing over the offline+vendored path (then don't ship the network dependency).

**Recording:** `efficacy_run` rows + a `reflex.efficacy`-style estimate per recipe;
`meta.json.scaffold` per session; a short results table appended here and to TOOLS.md.

---

## 7. Risks & mitigations

| Risk | Mitigation |
|---|---|
| Network dependency mid-run | Offline-first (§1); online tier opt-in + vendored fallback + reachability probe |
| Template ⇄ model file collision | Reconciliation rules (§3.3): scaffold owns config, model owns source |
| Overfitting / dojo dishonesty | Capability-only detection + general-trigger test (§5, §6) |
| Masking model capability | Record the **L2** level; never compare a scaffolded pass to an L0 baseline (§5) |
| Template version drift | Pin template versions; record in `meta.json.scaffold`; vendored fallback is frozen |
| Regression on unanticipated stacks | Control set in the A/B; recipes match conservatively; `MU_SCAFFOLD_STACKS` scoping |
| Harness change during a live collection | Implement/measure only between runs; gate the next 8 h run on the launcher preflight (test suite + smoke) |

---

## 8. Work breakdown (checklist)

- [ ] Phase 0: baseline measurements (p1,p2,p4,p5,p6,p9,p10 × 15), recorded.
- [ ] `scaffold.py`: stack detector + declarative recipe table (offline tier first).
- [ ] Ground-time hook in `agent.py`/`plan.py` behind `MU_SCAFFOLD`; PLAN.md reconciliation; `meta.json.scaffold`.
- [ ] Unit tests: detection generality, offline guarantee, reconciliation, idempotence, graceful degradation.
- [ ] `mu check` scaffold-readiness; `mu setup` optional pre-warm + Vite vendored fallback under `dojo/scaffolds/`.
- [ ] Phase 3 treatment measurements (offline; online for p9).
- [ ] Phase 4 analysis (Beta-Binomial Δ + CIs); KEEP/DROP decision per pre-registered criteria.
- [ ] Update docs: TOOLS.md (mark `dotnet new`/`cargo new` ✓, `create-vite` per outcome), affected `docs/problems/*` and `docs/challenges/csharp-aspnet-scaffolding.md` status, docs/challenges/README.md, TODO.md.

## 9. Done criteria

The change ships **on** for a stack iff its A/B meets the §6 KEEP criteria with no control
regression; otherwise it stays behind `MU_SCAFFOLD` (off) with the negative result recorded
here. Either way, the offline guarantee (§1) holds and the honesty tests (§5) pass.
