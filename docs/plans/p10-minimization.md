# Plan: minimizing & de-risking the p10 problem space

_A design report on making **p10-dotnet-vue-blog** — the dojo's one persistently
0-pass problem — either smaller (less for the model to decide) or more
deterministic (less run-to-run variance). Three approaches, a comparison
framework, a recommendation with an optimality argument, and an implementation
plan. Status: **proposed**. Written 2026-06-19._

---

## 0. Why p10 is the open problem

p10 asks for a coordinated two-project full stack in one shot: an ASP.NET Core
minimal API with EF Core/SQLite, a seeded `Post` model, `GET /api/posts`, an
**xUnit `WebApplicationFactory` integration test**, *plus* a Vue 3 + Vite + TS
frontend with a **Vitest fetch-mocking test**, wired by one Makefile. It runs in
architect (staged) mode — backend, frontend, integration as separate sessions
([`_detect_stages`](../../src/mu/agent.py)).

Measured (run 7, qwen2.5-coder-7b, ctx 6000): **0/12**, median 6 repair iters,
~33k prompt tokens/run — the heaviest and least reliable problem in the set.
Dominant errors:

| Error | Count | Class |
|---|---|---|
| CS0101 duplicate type in global namespace | ×14 | cross-stage **coordination** (types redefined across files) |
| MSB1003 no project/solution at the test dir | ×8 | **structure** (where `dotnet test` runs) |
| CS0053 inconsistent accessibility (public API exposes internal EF type) | ×8 | **coordination** (type-ownership / visibility) |

### The decisive prior: a general scaffolding A/B already found structure isn't the binding constraint

**State in this tree (verified 2026-06-19):** `src/mu/scaffold.py` exists but is
the **detection + recipe core only**, *unwired* (commit `48fa0c8`,
"iteration 1… unwired, gated, offline-first"). Nothing in the hot path imports
it; there is no per-stage hook and no committed A/B. [scaffolding.md](scaffolding.md)
§6 is the *evaluation plan*, not results.

A later line of work (recorded in project memory `project-scaffolding-impl`, on a
branch **not merged here**) wired it per-`run`, fixed an ordering bug so the
scaffold actually fired, and ran a pre-registered A/B whose verdict was **DROP**:

> p10 A/B (scaffold confirmed firing): baseline **0/8** vs treatment **0/8** — no
> movement, and repair-iters *rose* 0.8 → 2.2 (a cost regression). Backend
> scaffolding fixes MSB1003/CS0017 **but not p10's real ceiling**: the frontend,
> the WebApplicationFactory integration test, and multi-project coordination.

Treat this as a **strong working hypothesis**, not in-tree fact: the structural
failure classes (MSB1003, csproj shape) are likely **not** the binding
constraint — adding backend structure-by-construction moved nothing. So any new
proposal must be judged on whether it attacks **coordination** (CS0101/CS0053)
and the **frontend/integration logic**, not just structure. Approach B (§1) is
designed precisely to *confirm or refute* this hypothesis in-tree before we spend
on A or C.

### What the 2026 literature says

The current external picture lines the three approaches up almost exactly:

- **Spec-/contract-driven development** treats a structured spec as the source of
  truth and separates planning from implementation; structured input measurably
  reduces hallucination ([Thoughtworks 2025][tw], [GitHub spec-kit][ghspec],
  [arXiv 2602.00180][sdd]). → Approach **C**.
- **Skeleton/template-guided repository generation** ships a target skeleton (and
  often the tests) and has the model fill only the dynamic parts; hybrid
  *parameterized templates* enforce structure while the LLM infers logic
  ([Skeleton-Guided-Translation, arXiv 2501.16050][skel]; RepoZero; Transrepo-Bench).
  → Approaches **A** and **B**.
- **TDD-style pinning**: giving the test as the contract is "a fundamental
  determinant of success"; ~40% of agent-generated code still fails to match the
  deterministic reference even when it executes ([TDD-Bench, arXiv 2505.09027][tdd]).
  → Approach **B** (L3 rung).
- **Cascade control / atomic decomposition**: "error propagation is the primary
  bottleneck in agent reliability"; the mitigation is to decompose into the
  smallest subtasks and gate each, so an early mistake can't compound
  ([Constraint decay, arXiv 2605.06445][decay]; [Where LLM Agents Fail, arXiv
  2509.25370][fail]). This is *exactly* p10's repair-oscillation failure mode.
  → Approaches **B** (independent gates) and **C** (type-ownership ledger).

The minimization ladder mu already defines ([DOJO.md](../../DOJO.md)) is the local
name for this literature: **L0 open → L1 contract → L2 scaffold → L3 test-pinned →
L4 fill-in.** The three approaches below are three different rungs/mechanisms on
that ladder.

---

## 1. The three approaches

### Approach A — Stage-aware runtime scaffolding (general, L2)

**Idea.** Resurrect the dropped scaffolder, but fix the design flaw that killed
it: make it **per-stage**. Today `scaffold.detect()` returns `dotnet-webapi`
first, so on the staged path it fires once (on the model stage) and the csproj it
leaves blocks every later stage's own scaffold (`dotnet new` exits 73 on a
non-empty dir). Make detection a function of the **current stage**: backend →
`dotnet new webapi` + EF refs; integration → `dotnet new xunit` referencing the
backend; frontend → vendored `vite-vitest` skeleton. Each stage gets the
canonical skeleton from an official template; the model writes only the source
and test bodies.

**External basis.** Skeleton-guided repository generation; hybrid parameterized
templates ([2501.16050][skel]).

**Implementation.**
- `src/mu/scaffold.py`: change `detect(Signal)` → `detect(Signal, stage)`; add a
  `vite-vitest` recipe (online `npm create vite` *plus* a frozen vendored copy in
  `dojo/scaffolds/vite-vitest/` for the offline guarantee, per scaffolding.md §1).
- `src/mu/agent.py`: call `_maybe_scaffold(stage=...)` at the **start of each
  staged session** (the architect loop), not once globally; keep it before
  `ground_plan` so the reconciliation in scaffolding.md §3.3 holds (scaffold owns
  `*.csproj`/config, model owns `.cs`/`.vue`/`.test.*`).
- Record `meta.json.scaffold = {stage, recipe, files, tier}` so analysis can
  separate scaffolded from from-scratch passes.
- Stays behind `MU_SCAFFOLD` until an A/B earns a default flip.

**Pros.** General and honest (capability+stage keyed, never the problem id);
offline for the backend; the detection + recipe core already exists
(`scaffold.py`); eliminates MSB1003 and the csproj-shape classes by construction;
makes runs *cheaper* if it works. (Caveat: the wiring, the per-stage `detect`, and
the vendored Vite fallback are **not** in this tree yet — see §0.)

**Cons.** The A/B prior says backend structure is **not** the binding constraint,
so the upside hinges entirely on the *new* frontend recipe + correct stage
routing actually attacking the frontend/integration ceiling — unproven. Adds a
(vendored-mitigated) network surface. Does **not** touch CS0101/CS0053
(coordination) or test logic. Template version drift to maintain.

### Approach B — Committed fixture staircase (per-problem, L2 → L3 → L4)

**Idea.** Use the shipped fixture mechanism ([`fixtures.apply`](../../src/mu/fixtures.py),
`dojo/fixtures/<id>/`, the `minimize` field in
[problems-catalog.json](../../problems-catalog.json)) to give p10 progressively
more of its own correct boilerplate, and **measure at each rung** to find where
it starts passing. This does not try to make the agent better; it makes p10 a
*deterministic instrument* and **localizes the binding constraint**.

The rungs (each = the previous plus more given files):

| Rung | Given as fixtures (model skips) | Model still writes | Isolates |
|---|---|---|---|
| **L2** | both `*.csproj`, `Makefile`, `frontend/{package.json,vite.config.ts,tsconfig.json}` | `Program.cs`, xUnit test, `App.vue`, `*.test.ts` | structure removed → logic+coordination+test-authoring |
| **L3** | + the xUnit test file + the Vitest test file | `Program.cs`, `App.vue` | + test-authoring removed → implementation + coordination only |
| **L4** | + `Program.cs`/`App.vue` stubs with fixed signatures | function/handler bodies | the irreducible logic core |

**External basis.** TDD-pinning ([2505.09027][tdd]); skeleton-with-tests
repository benchmarks (Transrepo-Bench); atomic decomposition with independent
gates ([2605.06445][decay]).

**Implementation.**
- Author `dojo/fixtures/p10/` once, by hand, as *correct* boilerplate (committed
  via the `.gitignore` golden-file exception fixtures already use).
- Extend `fixtures.apply` to be **level-aware**: read `minimize` for the problem
  and copy only the subset for that rung (e.g. lay fixtures out as
  `dojo/fixtures/p10/L2/…`, `…/L3/…` deltas, and apply L≤target). ~20 lines.
- The agent already marks any pre-existing planned file done (`agent.py` ~648),
  so given files vanish from the writer's job automatically.
- Record the rung in `problems-catalog.json` and in `meta.json`, so a pass is
  always reported *with its level* (an L3 95% is not an L0 95%).

**Pros.** The **only** approach guaranteed to move p10 off 0 (pin enough and it
must pass), and — decisively — it **tells you which layer is the real ceiling**,
which neither A nor C can do blind. Uses shipped, tested code (near-zero new
attack surface), fully offline, fully deterministic, gives graded continuous
signal. Each rung is an independent gate, the literature's prescribed cascade
mitigation.

**Cons.** Fixtures are **per-problem**, the honesty tension: an L3/L4 pass
measures implementation, not the open-ended capability. It's a *diagnostic /
measurement* lever, not a shipped product improvement — by itself it doesn't make
the real agent better on novel full-stack goals. Must be scrupulously labelled by
L-level or it misleads.

### Approach C — Deterministic full-stack contract + type-ownership ledger (general, L1)

**Idea.** Attack the *coordination* ceiling directly. Extend the architect so
that, for a detected full-stack stack (`_is_multilayer` + dotnet&node), it emits
a **deterministic contract** — fixed file manifest with paths, the API route and
JSON shape, the canonical test command, and a **single-owner type ledger**: each
shared type (`Post`, the `DbContext`) is declared to live in exactly one backend
file and be `public`, referenced (never redefined) by the test stage. Pair it
with a deterministic cross-stage guard that, before the integration gate,
**removes any type re-defined in a second stage file** and flags a `public`
member exposing a non-`public` type — i.e. promote a generalized, contract-driven
version of the existing `run_staged orphan cleanup` so CS0101/CS0053 cannot
survive to the compiler.

**External basis.** Spec-/contract-first development ([2602.00180][sdd],
[spec-kit][ghspec]); atomic-provenance to stop error cascades ([2606.07937][casc],
[2509.25370][fail]).

**Implementation.**
- `src/mu/plan.py` / architect: a declarative full-stack contract template
  (capability-keyed) injected into `ARCHITECTURE.md`/PLAN.md — manifest + route +
  JSON + test command + the type-ownership table. Pure L1 (no files written).
- A new deterministic step (a reflex or a staged-gate guard in `agent.py`):
  scan all stage `.cs` for a `class/record <T>` declared more than once across
  files → keep the backend-owned one, delete the duplicate (CS0101); detect a
  `public` signature returning/exposing a type whose declaration is not `public`
  → raise the type to `public` (CS0053). General class, no problem id.
- Keep the architect change behind a flag for the A/B.

**Pros.** The only approach that targets p10's *actual* dominant errors
(CS0101/CS0053 coordination, ×22 combined) and is **general** — a full-stack
contract + type-ownership guard helps any multi-project .NET goal, not just p10,
so it's honest *and* a real product improvement. Reduces repair oscillation at
its root (the cascade) per the cited failure-analysis work.

**Cons.** The most design work and the most new attack surface (architect
template + a cross-stage AST-ish guard that must not delete a legitimately
distinct type). An L1 contract still leaves the model to author every file, so
variance stays high — it may shrink the *error classes* without yet crossing the
pass threshold (the frontend/integration logic ceiling remains). Highest risk of
a subtle wrong-deletion regression on control problems (p4).

### What all three share — the common substrate (build this first)

A, B, and C are not three unrelated ideas: they are **the same minimization
ladder**, differing only in *how* the fixed part of the project is produced
(runtime template / committed fixture / contract spec) and *how much* of it is
fixed. So they rest on one substrate, and most of the real engineering lives
there, not in the approach-specific veneer:

| Shared component | A | B | C | Where it lives |
|---|:-:|:-:|:-:|---|
| Full-stack stack **detector** (dotnet+vue, capability-keyed) | ✓ | ✓ | ✓ | `scaffold.Signal`/`detect`; `_is_multilayer` |
| **"Provided = done" reconciliation** (mark fixed files done; model can't clobber/redeclare them) | ✓ | ✓ | ✓ | `agent.py:678` |
| **Cross-stage type-ownership guard** (CS0101/CS0053 — the #1 p10 error) | ✓ | ✓ | ✓ | new csharp reflex (§A.3) + `run_staged` orphan cleanup |
| **Honest per-layer gates + the k/4 metric** | ✓ | ✓ | ✓ | `measure.py` `_k4`; `_test_passed` |
| **L-level / `meta.json` bookkeeping** (a pinned pass ≠ an L0 pass) | ✓ | ✓ | ✓ | `problems-catalog.json` `minimize`; `meta.json` |
| **One frozen structure artifact** (`dojo/scaffolds/` == fixtures `L2` == C's golden reference) | ✓ | ✓ | ✓ | new shared dir |
| **Offline-first** (no hard network dependency) | ✓ | ✓ | ✓ | vendored fallback |

The decisive observation: **the artifacts compose.** B's `dojo/fixtures/p10/L2`
structure *is* the vendored skeleton A copies offline *is* the golden reference
C's type-ledger guard validates against. Author it once; all three consume it.

### Improvements needed in all three cases (the no-regret backlog)

These are worth doing **before** committing to A, B, or C — each is a prerequisite
for *all three* and for even comparing them, and the first two carry their own
weight even if every approach is later dropped:

1. **S1 — Honest per-layer gates (do first).** The k/4 metric is only trustworthy
   if each layer's gate detects a *vacuous* pass. The work already shipped covers
   `make` (`_make_vacuous`); p10's real gates are `dotnet test` and
   `npx vitest run`, which have their own silent-success shapes: `dotnet test`
   with **0 tests** (no test discovered), a build that *fails* but the wrapper
   exits 0, and `vitest` reporting **"No test files found"**. Extend the
   vacuous-detection family to these. Without S1, all three approaches are scored
   against a lying instrument. **No-regret: it makes the whole harness honest
   regardless of A/B/C** (same class as the p7 false-pass fix).
2. **S2 — Cross-stage type-ownership guard (highest leverage).** CS0101 + CS0053
   are ×22 of p10's errors and bite all three: a scaffold leaves a `Program.cs`
   the model also writes; a fixture pins a `Post` the model re-declares; a
   contract *names* the owner but can't stop a redeclaration. A deterministic,
   general guard (keep the backend-owned definition, delete cross-stage
   duplicates; raise a type behind a `public` signature to `public`) is needed
   under every approach. **No-regret: it's a general multi-project-.NET reflex
   that also helps p4**, independent of any minimization lever.
3. **S3 — One reconciliation routine.** Generalize `agent.py:678` into a single
   "this set of paths is fixed; the model owns the rest, and must neither rewrite
   nor redeclare them" contract that A (scaffold-owned), B (fixture-owned), and C
   (contract-owned) all call with a different file set. Avoids three subtly
   different mark-done implementations drifting apart.
4. **S4 — One detector + level bookkeeping.** A shared `is_fullstack_dotnet_vue`
   capability check and a `meta.json.minimize`/`scaffold` record, so every reported
   p10 pass carries its rung and no run is silently compared across levels (the
   central honesty risk for all three).
5. **S5 — Test-authoring skills for the two hard test types.** No *structural*
   lever (A, B-L2, or C) reaches the actual model ceiling: authoring a correct
   `WebApplicationFactory` integration test and a correct Vitest fetch-mock. All
   three need a complementary writer/architect skill for exactly these two shapes,
   or they top out one layer short (B only crosses it by *pinning* the tests at
   L3 — which is the diagnostic that tells you whether S5 is even worth writing).

Sequencing falls out of this: **S1–S4 are Phase 0 of any path**, and they are the
cheapest to exercise through Approach B (which needs no runtime templates or
architect changes to drive the whole substrate end-to-end). That is an
independent reason the recommendation lands on B-first (§3): it is the minimal
harness that lights up the shared substrate so A or C can be chosen against data.

---

## 2. A capability model, and how to compare the three

### 2.0 A capability model: why each step raises P(solve all 10)

The whole plan needs one quantitative spine: a model in which *every* useful step
provably raises the chance of solving the problems, whose attributes are the
levers above (reduction, reflexes, model, variance), and which is estimable from
what mu already logs. mu's staged, gated architecture gives it for free.

**Layers (a series/chain system).** Problem *i* is verified by `L_i` independent
gates — its *layers*. p10 has `L=4` (backend build, backend test, frontend build,
frontend test); a trivial problem has `L=1`. mu solves *i* iff it clears **every**
layer: a series system in reliability terms.

**Per-layer success (item-response form).** Layer `(i,ℓ)` clears with probability

  q_{iℓ} = σ(z_{iℓ}),  σ(x)=1/(1+e^{−x}),
  z_{iℓ} = θ·a_ℓ − δ_{iℓ} + Σ_k β_k·x_{kiℓ} − γ·V_{iℓ}

a logistic "ability − difficulty" margin (standard IRT). Attributes and what moves
each:

| symbol | meaning | moved by |
|---|---|---|
| `θ` | model ability (per model, opt. per toolchain) | model choice / routing |
| `δ_{iℓ}` | intrinsic difficulty / *size* of the subproblem at layer ℓ | **problem-space reduction** (self-scaffold, contract, slicing) |
| `β_k ≥ 0` | strength of capability/step *k* | reflexes, skills |
| `x_{kiℓ}` | coverage: does step *k* touch layer (i,ℓ) (its **breadth**) | generality of the step |
| `γ·V_{iℓ}` | variance penalty (degeneration, planner noise) | guards, seed, prompt-cache |
| `a_ℓ` | layer discrimination | (structural) |

**Objective.** `P_i = ∏_ℓ q_{iℓ}` (solve problem *i*); `E[#solved] = Σ_i P_i`;
the strict "solve all ten" `P_all = ∏_i P_i`. All three are strictly increasing
in every `q_{iℓ}`.

**Result 1 — each step provably raises the likelihood (monotonicity).** `z` is
increasing in `θ` and each `β_k` (with `x≥0`), decreasing in `δ` and `V`; `σ` is
strictly increasing. So any step that raises `θ`, adds a `β_k≥0`, lowers a `δ`, or
lowers a `V` — *without lowering another layer's `z`* — strictly increases the
affected `q_{iℓ}`, hence `P_i`, `E[#solved]`, and `P_all`. That is the exact
meaning of "each step improves the likelihood," and of **no-regret**: a step is
no-regret iff `Δz_{jℓ'} ≥ 0` everywhere (it lowers no layer of any problem — the
control-set non-regression rule).

**Result 2 — the chain makes the *weakest* layer decisive (and explains the
dropped scaffolder).** `∂P_i/∂q_{iℓ} = ∏_{ℓ'≠ℓ} q_{iℓ'}`. The marginal value of
improving layer ℓ is the **product of the other layers' pass probabilities** — so
if any other layer ≈ 0, improving ℓ barely moves `P_i`. For p10 (all four layers
low) raising only the backend layer leaves `P_i ≈ 0`: precisely the measured 0→0
of backend-only scaffolding. For a 0/L problem the binding move is to lift the
**minimum** layer — maximize `min_ℓ q_{iℓ}` (a bottleneck / max-min objective) —
until every factor exceeds 0. In log space `log P_i = Σ_ℓ log q_{iℓ}`; the k/4
score (§2.1) is a coarse threshold-count proxy for this sum, and `argmin_ℓ q̂_{iℓ}`
names the layer to attack next.

**Result 3 — reduction has the highest leverage when the model is weak (sigmoid
steepness).** `dq/dz = σ(z)(1−σ(z))` peaks at `z=0` (`q=0.5`) and is tiny in the
tails. A layer at `q≈0` sits deep in the negative tail, so a *single* step barely
moves it — you must **stack** steps (`Σβ`, `Δδ`) to drag `z` from very negative
toward 0 before returns appear. Hence p10 needs a *portfolio* of reductions, not
one reflex, and progress is invisible in binary pass (`z: −5→−2`, `q` still ≈0)
yet visible in a finer metric — the formal case for k/4. It also says: when `θ` is
small and `δ` large (a weak local model on a big subproblem — **mu's regime**),
lowering `δ` gives the biggest `dq`, because it moves `z` toward the steep region.
That is the mathematical reason mu's edge is problem-space reduction + reflexes,
not a bigger model.

**Tradeoffs (read straight off the model).**

1. **Reduction vs. capability — the honesty tradeoff.** External fixtures lower
   `δ_{iℓ}` for one problem at a declared level but add no transferable `β` and
   don't raise `θ`: they buy `P_i` without raising ability. The **L-level *is* the
   amount of `δ` removed externally**; a pass at lowered `δ` ≠ a pass at full `δ`.
   mu's *own* reduction lowers `δ` through a general mechanism — a real capability
   gain. (This is the math behind "fixtures are measurement, not product.")
2. **Generality vs. risk — `β` breadth vs. overfit.** A step with `β>0` on its
   target but `β<0` elsewhere (overfit, wrong-deletion) lowers some `q`. Net
   `ΔE[#solved] = Σ_helped − Σ_hurt`; ship iff net > 0 and no control layer
   regresses (the `sz5_gate` rule).
3. **Variance vs. cost.** Lowering `V` raises `q` but costs exploration/tokens,
   and `σ` saturates as `q→1`, so each added repair pass or reflex has diminishing
   `dq` at fixed cost `ΔT`. Ship while `Δq·(∂P/∂q)/ΔT > threshold`.
4. **Depth vs. breadth.** For a 0/L problem, concentrate on the bottleneck layer
   (Result 2); for a near-solved problem (all `q` high), spread — pick the broadest
   `β` (largest `Σ_i x_{kiℓ}`, helping the most problems at once).
5. **`θ` vs. `(δ,β)`.** Raise solve-prob with a bigger model (`θ↑` uniform, but
   cost/swap on 8 GB) or with reduction+reflexes (`δ↓`, `β↑`, targeted, free
   locally). Result 3 says the latter dominates in mu's weak-`θ`/large-`δ` regime.

**It's estimable from what mu already logs** (so the model is a fit, not an
abstraction): `q̂_{iℓ}` = clears/`N` per layer — *honest only if S1 makes the gate
reject vacuous passes*; `θ ≈` the KB `competence_by_toolchain`; `β ≈` a reflex's
`efficacy` Δ; `V ≈` stochasticity `1−modal/N`; the Beta-Binomial `observe.Posterior`
gives `q̂` with uncertainty and `sz5_gate` tests `Δq`. The model is a logistic fit
over `firings.jsonl × outcomes`. The metric (§2.1) and the step-selection rule
(§A.4) are direct read-outs of it.

### 2.0.1 Fitting it — the one component all three approaches share

The "benefits all three" that matters here is **the three approaches A/B/C**: they
should not each grow their own analysis, but call one fitted object that measures
the agent, ranks the next step, and routes. (As a bonus, that same object pools
across the LLM models mu runs — granite/qwen-3b/qwen-7b — so estimates transfer;
see the `θ_m`/`β_k` note below. Secondary to the approaches.)

The model earns its keep only if it can be *fitted from dojo data* and *queried by
A, B, and C through one interface*. Both fall out of the parameterization.

**The fittable form (hierarchical logistic).** Pool every `(model m, problem i,
layer ℓ, run)` outcome `y∈{0,1}` and fit `logit q = θ_m·a_ℓ − δ_{iℓ} + Σ_k β_k
x_{kiℓ}` with partial pooling:

- `θ_m` per LLM model (granite-3b, qwen-3b, qwen-7b) — a few parameters.
- `β_k` per step, **shared across problems and models** (`β_k ~ N(β̄_k, τ²)`).
  Partial pooling (bonus): a reflex's effect measured on qwen *informs* its effect
  on granite — and granite's data is sparse. A truly general reflex shows a tight
  `β` across models; one that only rescues a weak model shows a per-model deviation.
- `δ_{iℓ}` per (problem, layer), with a prior tying layers *of the same kind* (all
  "build" layers, all "test" layers) so a new problem borrows strength.

**Honest identifiability.** 10 problems × 1–4 layers × 3 models is *thin* for a
joint fit with dozens of `β`. So the practical estimator is **two-level, reusing
machinery mu already has**, not a from-scratch MCMC:

1. **`q̂` per (m,i,ℓ)** by Beta-Binomial smoothing — exactly `observe.Posterior` —
   a mean + CI from few runs (needs the S1 honest gates, or `q̂` is biased high).
2. **`β_k` per step** from the **ablation/efficacy Δ** mu already computes
   (`efficacy_run`, `sz5_gate`): the change in `q̂` when the step is disabled,
   pooled over the layers it covers (coverage `x` read from `firings.jsonl`).
3. **`δ` from the B staircase**: each rung lowers `δ` for the pinned layers, so the
   jump in `q̂` between `L(k)` and `L(k+1)` *is* an estimate of that layer's `δ`
   contribution. Approach **B is literally the experiment that identifies `δ`** —
   its only honest role.

**One component, three consumers.** Put this behind `src/mu/capability.py` (a thin
layer over `observe.py`/`reflexdb.py`) exposing `q_hat`, `p_solve`, `bottleneck`,
`rank_steps`, `route` (§A.5). Then the *same object* drives all three approaches:

- **A** asks `bottleneck(m,i)` and self-scaffolds a layer only when
  `expected_solve_gain > 0` (its siblings aren't ≈0) — targeted, not blind; the
  direct fix for the 0→0 backend-scaffold result.
- **B** *produces* the `δ` estimates the component needs, then retires to a
  regression signal once fitted.
- **C** is selected and justified by its reflex's `β·breadth` and ranked by
  `expected_solve_gain` on the coordination layer; the contract's `δ`-reduction is
  predicted, then checked against the refit.
- **Routing for all three LLM models** is `route(m,i): p_solve(m,i) < ε` — the
  layer-level generalization of `fixtures.should_skip`, with granite borrowing
  qwen's pooled `β`.

So the model is not three analyses bolted onto A/B/C: it is **one fitted object
that measures the agent, ranks the next step, and routes the weak models**, which
every approach (and the `practice` training loop) calls. That single
implementation is the concrete "benefits all three."

### 2.1 The headline instrument: layer-resolution score (k/4)

Binary p10 pass-rate is **0** and therefore uninformative — it cannot rank three
interventions that all start from 0 (Result 2/3: their gains hide in the negative
tail). The comparison uses **graded, continuous signal** — the per-layer `q̂` and
the chain solve-prob the model defines — exactly as the efficacy machinery already
does for reflex ablations (`observe.Posterior` Beta-Binomial, `sz5_gate`,
`efficacy_run`; AGENTS.md §5z).

Define four checkpoints the harness can already read from the stage logs:

1. **Backend builds** — no CS/MSB errors from `dotnet build`.
2. **Backend+integration test passes** — `dotnet test` green (the
   WebApplicationFactory `GET /api/posts` → "Hello World").
3. **Frontend builds / type-checks** — `vite build` / `tsc` clean.
4. **Frontend Vitest passes** — mocked-fetch render assertion green.

`p10 pass` ⇔ all four. The comparison metric is **mean k/4 reached per run** — a
continuous score that *moves* while binary pass is pinned at 0, and that
**localizes** where each approach helps (A should lift #1; B at L3 should lift
#1–#2; C should lift #2/#3 by killing the coordination cascade). This is the
single most valuable thing to build for this work and it is reusable for any
staged problem.

### 2.2 Arms and metrics

| Arm | Level | Flag/mechanism |
|---|---|---|
| Baseline | L0 | none (today) |
| A | L2 | `MU_SCAFFOLD=1`, stage-aware |
| B-L2 / B-L3 / B-L4 | L2/L3/L4 | `dojo/fixtures/p10` + `minimize` |
| C | L1 | architect contract + type-ledger guard, flagged |

Per arm, ≥15 fresh-plan runs (`mu dojo measure p10 -n 15` — fresh plan captures
planner variance), recording:

- **mean k/4** (headline, continuous) and its bootstrap 95% CI;
- pass-rate Δ vs baseline with **Beta-Binomial 95% CI** + `sz5_gate`;
- **stochasticity** `1 − modal/N` (the determinism axis the ladder targets);
- median **repair-iters** and **tokens/run** (cost; the dropped scaffolder
  *raised* these — a real signal);
- **first-stage-of-failure** histogram (which checkpoint each run dies at).

### 2.3 The decision rubric (pre-registered, weighted)

Score each arm on five axes; **honesty is a gate, not a weight**:

| Axis | Weight | What wins |
|---|---|---|
| Lifts p10 (CI lower bound of pass-rate > 0, or mean k/4 ↑ with CI∉0) | 0.35 | the headline |
| Determinism (stochasticity ↓) | 0.20 | a tighter, more reproducible instrument |
| Cost (repair-iters & tokens ↓, not ↑) | 0.15 | cheaper runs |
| Generality / product value (helps novel goals, capability-keyed) | 0.20 | A, C |
| Implementation + maintenance cost (low = better) | 0.10 | B |
| **Honesty gate** (label L-level; controls p1/p2/p5/p6 Δ CI ∋ 0) | gate | any arm that regresses a control or misreports its level is disqualified |

Continuous metrics (k/4, iters, tokens) decide with far fewer runs than binary
pass/fail — the explicit reason to build §2.1.

---

## 3. Recommendation

**Objective (the lens for everything below): make _mu_ better — and the specific
capability to build is that _mu itself knows how to make its own problem space
smaller_.** The minimization ladder (L0–L4), the fixtures, the scaffold, the
contract are, as written elsewhere in this plan, things *we* do **to** the problem
from outside. That makes p10's *number* move; it does not make the **agent**
better. The durable win is to move that skill **inside mu**: faced with a big,
ambiguous, multi-layer goal, the agent should itself reduce it — scaffold the
structure, write a contract it then honours, decompose into the smallest
independently-verifiable slices, and build them up gated one at a time — so the
*model* only ever faces a small, low-variance subproblem. p10 is the **test
case**; an agent that reduces its own problem space is the **product**.

Handing mu correct files (a fixture) can make p10 *pass* without teaching mu
anything; per the codebase's own rule a fixture is "correct boilerplate given to
the model, not an answer key" — a *measurement* device, external to the agent. So:

- **Capability deliverables (these are "mu getting better"):** the general,
  capability-keyed mechanisms — **S2** (cross-stage type-ownership reflex), **C**
  (the L1 contract that shrinks what the model must decide on *any* full-stack
  goal), **S5** (WebApplicationFactory + Vitest test-authoring skills), and **A**
  (scaffolding) if structure turns out to bind. These help every matching goal,
  not just p10.
- **Diagnostic only (not a deliverable):** **B**, the fixture staircase. It does
  not improve the agent; it *localizes the ceiling* cheaply so the capability work
  is aimed correctly. Its fixtures persist only as a labelled-L-level regression
  signal, never as a capability claim.

Recommended order:

1. **Ship S2 now — a real agent improvement.** A general cross-stage
   type-ownership reflex is exactly mu's thesis (a deterministic fixer for a
   general error class); it kills p10's #1 error (CS0101/CS0053, ×22) *and* helps
   p4, with no minimization at all. Pair with **S1** (honest `dotnet test`/`vitest`
   gates) so any gain is measurable rather than vacuous.
2. **Run the B/k4 probe** (§2.1) — instrumental, run-once, then set aside. Measure
   p10 at L0/L2/L3/L4 and read the rung where mean k/4 jumps:
   - **jumps at L2** → structure binds → build **A** (general scaffold);
   - **jumps at L3** → coordination + test-authoring binds → build **C** (contract)
     and **S5** (test skills) — the capability work, *not* the fixtures;
   - **only at L4** → irreducible model-logic ceiling → don't build A/C; route p10
     (`MU_ROUTE`) and keep the L3 fixture purely as a regression signal.
3. **Build the capability lever the probe named** (C+S5, or A), A/B it against the
   controls, ship-on only if it improves mu at **L0** (the open problem), not just
   at a pinned rung.

The mental check for every item: *would this help mu on a novel full-stack goal it
has never seen?* S2/C/S5/A pass it; B does not — which is exactly why B is a probe,
not the product.

### 3.1 Internalize it: the agent's own reduce-then-solve loop

Read through the objective, the three approaches are not separate features — they
are the **moves of one capability mu should own**: a *reduce* pass that runs before
the writer on any goal `detect_complexity` flags as hard/multi-layer, drawing on
the same toolbox a human uses to climb the ladder, but invoked **by the agent**:

| External lever (today) | Internalized as a mu capability |
|---|---|
| A — we scaffold from a template | **mu self-scaffolds**: detects the stack and lays its own skeleton (the `scaffold.py` recipes, but *mu* deciding to) |
| C — we pin a contract | **mu writes its contract first**: manifest + single-owner type ledger + per-layer test command, then holds itself to it (extends the architect) |
| B — we hand it fixtures | **mu builds in vertical slices**: skeleton → one layer green at a gate → expand. The *spirit* of the staircase (smallest verifiable core first) with **no answer-keys** — this is the only honest internalization of B |
| (the cascade literature) | **mu decomposes** the goal into the smallest independently-gated subtasks and stops an error before it compounds |

So the product is a general **`reduce()` stage** in the agent loop: detect → self-
scaffold → contract + type-ledger → vertical-slice plan with a gate per slice →
writer fills the smallest next slice. `ground_plan` and architect mode are the
embryonic version of this; the work is to generalize and *train* it. Crucially,
**mu should learn _when_ to reduce and which move helps which stack** — the dojo
`practice` loop and the competence/KB are exactly the training signal for that, so
the reduction skill improves with data instead of being hand-tuned per problem.

This also relocates the harness's job: the dojo no longer *applies* minimization
(except B as a one-off probe) — it **measures and trains** mu's own reduction
(honest per-layer gates + k/4 + the KB). The agent owns making the problem small;
the harness only scores how well it does it.

---

## 4. Why this is optimal (the argument)

The objective fixes where *value* lives: only a **general capability** — mu
reducing its own problem space (§3.1) — counts. A fixture pass yields **zero**
capability value (it's measurement); so B's worth is purely the *information* it
gives about which capability move to build. With that, two decisions:

**What to ship.** S2 (the cross-stage type reflex) is a general agent improvement
*now* — it helps any multi-project .NET goal and p4, independent of p10's outcome,
so its EV is positive unconditionally. Ship it first. The larger reduction moves
(C/A/S5) have **low, unknown** P(success) *given the prior* (structure shown not
to bind; coordination only *plausibly* binds) and **high** build cost — building
either blind repeats the dropped-scaffolder mistake.

**How to choose among them.** B has **P(localizes the ceiling) ≈ 1** at **low**
cost (shipped mechanism) and is the *only* action that makes P(success) for C/A
*computable* instead of guessed — but it is a **probe, not a deliverable**: it
buys information, never capability. So the optimal sequence is *ship the no-regret
capability (S2) → probe cheaply (B/k4) → build the reduction move the probe names
(C+S5 or A)*. Front-loading C or A is dominated (most cost to learn the least, and
it already failed once); front-loading B as if it were the *answer* is the error
the objective rules out — it makes the number move without making mu better. This
is the same honest-harness discipline the codebase mandates
([AGENTS.md](../../AGENTS.md) §0, memory `project-false-pass-gate`,
`feedback-honest-dojo`): don't build a general mechanism until the data names the
class it must target — and don't mistake a measurement device for the product.

A secondary optimality: B is the only option whose *artifacts compose with* the
others — its fixtures double as the offline vendored skeletons Approach A needs
(`dojo/scaffolds/`) and as the golden reference Approach C's type-ledger guard is
validated against. So even when B leads to A or C, nothing built is wasted.

---

## 5. Implementation plan (stepwise, hardened)

### 5.0 Invariants every step preserves

Non-negotiable; each becomes a test so a violation fails CI, not a live run.

- **I1 Default-off.** Any agent-affecting change sits behind a flag defaulting
  off; with all flags off the run is **byte-identical** to today (`test_*_noop`).
- **I2 Offline.** No step adds a hard network dependency; an online tier degrades
  to a vendored copy or to baseline (probe + fallback).
- **I3 Honest level.** Every recorded pass carries its L-level in `meta.json`;
  no statistic ever compares across levels.
- **I4 No control regression.** p1/p2/p5/p6 pass-rate Δ has a 95% CI lower bound
  ≥ −ε (ε = 0.05). Any step that breaches it is reverted, no exceptions.
- **I5 Idempotent + graceful.** Every reflex/scaffold/fixture op is idempotent and
  never raises into the agent loop — a failure degrades to baseline.
- **I6 Pre-registration.** The KEEP/DROP statistic, N, and threshold are written
  here *before* the run; no post-hoc moving of the bar.

Each step is specified **Build → Files → Tests → Accept → Measure → Gate →
Rollback.** "Gate" is the condition to start the next step; "Rollback" is how to
undo with no residue.

### Phase 0 — shared substrate (no-regret; unblocks all of A/B/C)

**Step 0.1 — S1 honest per-layer gates** *(prerequisite for every measurement)*
- *Build:* add `_dotnet_test_vacuous` (0 tests discovered, or "Build FAILED" with a
  0 exit) and `_vitest_vacuous` ("No test files found" / 0 passed) to the
  `_make_vacuous` family; route the staged backend/frontend gates through
  `_test_passed`.
- *Files:* `src/mu/agent.py` (+ `tests/test_vacuous_dotnet_vitest.py`).
- *Tests:* each sentinel ⇒ fail; a genuine green log ⇒ pass (no false-negative); a
  genuine failing log ⇒ fail.
- *Accept:* replay archived p10/p4/p8/p9 `tests-final.log`s — **zero** genuine
  passes reclassified; every "0 tests"/"Build FAILED, exit 0" caught.
- *Measure:* count reclassified archive sessions (expect dotnet false-passes, the
  analogue of p7's `make` ones).
- *Gate:* ≥1 real reclassification **and** 0 false-negatives ⇒ proceed.
- *Rollback:* the sentinels are additive predicates; delete them.

**Step 0.2 — k/4 layer scorer** *(depends on 0.1)*
- *Build:* `_layer_clears` + `_capability_summary` (§A.4) in `measure.py`; emit
  `q_per_layer`, `p_solve_model`, `bottleneck`, `k_mean`.
- *Files:* `src/mu/dojo/measure.py` (+ test with archived-log fixtures).
- *Tests:* exact per-layer booleans on fixture logs; a missing/garbled log ⇒ "not
  cleared", never a crash.
- *Accept:* **self-consistency** — on the L0 archive, `p_solve_model` ≈ measured
  `pass_rate` within its CI (the chain product reproduces observed solves).
- *Gate:* self-consistency holds ⇒ the metric is trustworthy for ranking.
- *Rollback:* additive JSON keys; drop them.

**Step 0.3 — S2 cross-stage type-ownership guard** *(general capability; ship-worthy alone)*
- *Build:* `fix_csharp_cross_stage_duplicate_types` (keep the backend-owned
  definition, delete cross-stage duplicate blocks → CS0101) + a CS0053 sibling
  (raise a type behind a `public` signature to `public`); §A.3.
- *Files:* 2 reflex files under `src/mu/reflexes/csharp/`, `registry.py` catalog
  slot (`duplicate-declaration`), reapply wiring in `apply_csharp_repair_reflexes`
  and `_inter_stage_gate`.
- *Tests:* dup type across two stage files ⇒ one removed (backend kept); a
  **legitimately distinct** same-named type in a different namespace ⇒ **not**
  removed; CS0053 case ⇒ public; idempotent (double-apply stable).
- *Accept:* dry-run replay of archived p10 CS0101/CS0053 sessions ⇒ the guard
  resolves them.
- *Measure:* ablation — `mu dojo measure p10 -n 15 --disable
  fix_csharp_cross_stage_duplicate_types` vs enabled; β = Δ(backend-layer q̂)+CI;
  record an `efficacy_run` row.
- *Gate (KEEP):* backend-layer q̂ Δ CI lower bound > 0 **and** p4 not regressed (I4)
  ⇒ on by default. Else keep behind `MU_DISABLE_REFLEX`-style flag.
- *Rollback:* it's a catalogued reflex — the ablation path already removes it.

**Step 0.4 — S3/S4 reconciliation + detector + level record** *(behavior-preserving refactor)*
- *Build:* factor `agent.py:678` into `reconcile_provided(plan, owned_paths)`; add
  `is_fullstack_dotnet_vue(signal)`; write `meta.json.minimize`.
- *Tests:* provided files marked done; the model cannot re-add a provided type;
  detector fires on a synthetic full-stack goal, not on p1.
- *Accept:* with `owned_paths=∅` the refactor is byte-identical (I1); full suite
  unchanged.
- *Gate:* suite green, no behavior delta ⇒ proceed.
- *Rollback:* inline the function back.

**Step 0.5 — L0 baseline.** `mu dojo measure p10 -n 15` (post S1–S4); record
`efficacy_run` with per-layer q̂ — the reference every arm diffs against.

### Phase 1 — Approach B as the δ-identification probe (not a deliverable)

- **Step 1.1 — author fixtures** `dojo/fixtures/p10/{L2,L3,L4}`, each a *correct*
  rung-delta, offline and dependency-free.
- **Step 1.2 — level-aware `fixtures.apply`** (§A.2) + the runner apply hook; unit
  tests (right subset per rung, idempotent, off ⇒ no-op, I1).
- **Step 1.3 — measure the staircase** L2/L3/L4 at N=15; record per-layer q̂.
- **Step 1.4 — identify δ:** `δ̂_ℓ ≈ logit(q̂_ℓ at the rung that pins ℓ) −
  logit(q̂_ℓ at the rung below)`; the bottleneck is `argmin_ℓ q̂_ℓ` at L0/L2.

**Decision gate (pre-registered; I6).** With N=15 and the k/4 continuous CI:

| Observation | Inference | Next |
|---|---|---|
| jump at **L2**, bottleneck a *build* layer | structure binds | Phase 2a (A) |
| jump only at **L3**, bottleneck a *test* layer | coordination + test-authoring binds | Phase 2b (C + S5) |
| no jump until **L4** | irreducible model-logic ceiling | **kill A/C**; `route()` p10 (§A.5); keep L3 fixture as a regression signal only |

The L4 branch is an explicit **kill criterion** — the plan must be willing to
conclude "no minimization lever ships" and stop, rather than build A or C anyway.

### Phase 2a — Approach A *(only if the gate said "structure")*
- *Build:* `detect(Signal, stage)` (§A.1); `vite-vitest` recipe + vendored
  `dojo/scaffolds/vite-vitest/`; per-stage scaffold hook **before** `ground_plan`;
  `meta.json.scaffold`.
- *Tests:* stage-aware detection (frontend stage ⇒ vite, not webapi); offline
  guarantee (network blocked ⇒ vendored or baseline, no crash, I2); scaffold-then-
  ground reconciliation (no exit-73 collision); off ⇒ no-op (I1).
- *Measure/Gate:* A/B vs L0 baseline + controls; KEEP per §2.3 (p10 pass-rate CI
  lower bound > 0 or k/4 ↑ with CI∉0; controls hold, I4).
- *Rollback:* `MU_SCAFFOLD` off restores baseline.

### Phase 2b — Approach C *(only if the gate said "coordination + test")*
- *Build:* full-stack contract template in `_run_architect_pass` (manifest + route
  + JSON + test cmd + type-ownership table), capability-keyed, flagged. **Reuses
  S2** (already built in 0.3) as the deterministic backstop — the contract is
  advisory, the guard is enforcement, so the model ignoring the contract still
  can't ship CS0101.
- *Build (S5):* WebApplicationFactory + Vitest fetch-mock test-authoring skills,
  iff 1.4 localized the ceiling to test logic.
- *Tests:* contract injected only for full-stack goals; the S2 backstop fires when
  the model violates the type ledger; skills load for the right stack.
- *Measure/Gate:* A/B vs baseline + controls (esp. **p4**); KEEP per §2.3.
- *Rollback:* contract flag off; S2 stays (it's no-regret).

### Phase 2c — model calibration *(closes the loop; the key hardening)*
Before declaring any lever shipped: compare the capability model's **predicted**
effect (`expected_solve_gain` from the pre-ship fit) with the **measured**
Δp_solve post-ship. If `|predicted − measured|` exceeds the measurement CI, the
model is miscalibrated → **do not trust its rankings**: widen N, refit (§2.0.1),
and re-derive the next step. This prevents the model from becoming decorative and
turns §2.0 into a falsifiable predictor, not just a description.

### Phase 3 — record & generalize
- Update `docs/problems/p10-dotnet-vue-blog.md`,
  `docs/challenges/csharp-aspnet-scaffolding.md`, `TODO.md`, this plan's results
  table; **every figure carries its L-level** (I3).
- Promote any *general* capability that earned KEEP (S2; a contract/self-scaffold
  `reduce()` step) toward the product path per [feedback `agent_self_minimization`]
  — the dojo trained it, the agent keeps it.

### 5.1 Risk register

| Risk | Phase | Detector | Mitigation |
|---|---|---|---|
| Honest gate flags a *genuine* pass (false-negative) | 0.1 | archive replay shows a real pass reclassified | scope to exact sentinels; regression test on archived genuine passes; only on test gates |
| Log-parse drift across toolchain versions corrupts k/4 | 0.2 | self-consistency (Accept) breaks | parse stable substrings; unknown ⇒ "not cleared"; fixture-log tests |
| S2 deletes a legitimately distinct same-named type | 0.3 | the "distinct type not removed" test fails; p4 regresses (I4) | match exact duplicate blocks only, namespace-aware; ablation + control gate |
| Cross-level comparison inflates a result | all | a reported number lacks an L-level | I3 test: `meta.json.minimize` required; readme block prints the level |
| A's vite recipe needs the network mid-run | 2a | offline test fails | vendored fallback (I2); online tier opt-in + reachability probe |
| Model ignores C's contract | 2b | CS0101 reappears in logs | S2 backstop enforces deterministically regardless of the prompt |
| Capability model mis-ranks the next step | 2c | predicted vs measured Δ diverges | calibration gate (2c): refit before trusting rankings |
| p10 is pure model-ceiling; effort wasted | 1 | no jump until L4 | the L4 **kill criterion** stops A/C; route instead |

### 5.2 Statistical power & cost

Fresh-plan runs are the unit (planner variance included). A binary pass-rate shift
of 0→0.2 needs ≈ N=50 runs for a 95% CI to exclude 0; the **continuous** k/4 /
per-layer q̂ detects the same underlying shift at **N≈15** (§2.0 Result 3: progress
shows as `z` moving in the tail before pass flips), which is why every gate above
keys on k/4 first and confirms with pass-rate. Budget: p10 ≈ 200–300 s/run on the
8 GB M2 ⇒ a 15-run arm ≈ 1 h; the four Phase-0/1 arms (L0, L2, L3, L4) ≈ half a
day; reuse the `efficacy_run`/Beta-Binomial machinery rather than re-rolling stats.

---

## 6. Appendix A — worked code against the current tree

Illustrative, not final — each snippet names the real symbol it extends so the
diff is obvious. Verified against the tree at 2026-06-19.

### A.1 Approach A — wire the existing `scaffold.py` per stage

Today `scaffold.detect(sig)` ([scaffold.py](../../src/mu/scaffold.py)) returns the
first matching recipe globally, and nothing calls it. The fix is (1) make
detection stage-aware and (2) call it at the top of each staged session in
`run_staged` ([agent.py](../../src/mu/agent.py):2109). The off-path stays
byte-identical (`scaffold.enabled()` is `MU_SCAFFOLD=="1"`, default off).

```python
# src/mu/scaffold.py — make detection accept the stage the architect is on.
# 'backend' wants the web API (+EF), 'frontend' wants Vite/Vitest, the xUnit
# integration project rides with the backend stage.
_STAGE_PRIORITY: dict[str, tuple[str, ...]] = {
    'backend':  ('dotnet-webapi', 'dotnet-xunit', 'cargo-bin'),
    'frontend': ('vite-vitest',),
    'model':    ('dotnet-webapi', 'cargo-bin'),
}

def detect(sig: Signal, stage: str | None = None) -> Optional[Recipe]:
    """First recipe whose predicate matches. When *stage* is given, only recipes
    relevant to that stage are eligible (so the frontend stage can't be captured
    by the backend's dotnet-webapi — the bug that sank the first wiring)."""
    eligible = RECIPES
    if stage and stage in _STAGE_PRIORITY:
        names = _STAGE_PRIORITY[stage]
        eligible = tuple(r for r in RECIPES if r.name in names)
        eligible = tuple(sorted(eligible, key=lambda r: names.index(r.name)))
    return next((r for r in eligible if r.detect(sig)), None)
```

```python
# src/mu/agent.py — in run_staged()'s loop, BEFORE run() executes the stage.
# Build the capability Signal from the stage's own plan file (parse() gives the
# tasks + test command), scaffold, and let the existing fixture-detection at
# agent.py:678 mark the scaffold-owned files done.
from . import scaffold

for i, (stage_name, plan_file) in enumerate(active):
    ...
    if scaffold.enabled() and Path(plan_file).exists():
        sp = parse(plan_file)
        sig = scaffold.Signal(
            goal=goal,
            toolchains=frozenset(_infer_toolchains(sp)),   # from plan/test cmd
            test_command=sp.test_command or '',
            files=tuple(t.file_path for t in sp.tasks),
        )
        res = scaffold.detect(sig, stage=stage_name) and scaffold.scaffold(sig)
        if res:
            log("Scaffolded %s for stage '%s': %s", res.recipe, stage_name,
                ', '.join(res.files))
            _record_scaffold_meta(res, stage_name)   # meta.json.scaffold (audit)
    _stage_depth += 1
    try:
        rc = run(goal, model, plan_file=plan_file, force=True, max_iter=max_iter)
    ...
```

The vendored offline Vite fallback (so `vite-vitest` works air-gapped) is a frozen
copy under `dojo/scaffolds/vite-vitest/` that `scaffold()` copies when
`online_enabled()` is false — a few lines in `_run_recipe`, mirroring
[scaffolding.md](scaffolding.md) §1.4.

### A.2 Approach B — level-aware `fixtures.apply`

`fixtures.apply` ([fixtures.py](../../src/mu/fixtures.py)) currently copies *all*
of `dojo/fixtures/<id>/`. To climb the ladder, lay fixtures out as per-rung
deltas and apply every rung **up to** the problem's `minimize` level. The agent
already marks any pre-existing non-empty planned file done
([agent.py](../../src/mu/agent.py):678), so given files vanish from the writer's
job automatically — no agent change needed.

```
dojo/fixtures/p10/
  L2/  backend/Blog.csproj  backend.Tests/Blog.Tests.csproj
       frontend/{package.json,vite.config.ts,tsconfig.json}  Makefile
  L3/  backend.Tests/PostsApiTests.cs   frontend/src/App.test.ts   # the tests
  L4/  backend/Program.cs   frontend/src/App.vue                   # signature stubs
```

```python
# src/mu/fixtures.py
_LADDER = ('L0', 'L1', 'L2', 'L3', 'L4')

def _minimize_level(problem_id: str, catalog_path: str = 'problems-catalog.json') -> str:
    from mu.toolchain import load_problems_catalog
    for p in load_problems_catalog(catalog_path):
        if p['id'] == problem_id:
            return p.get('minimize', 'L0')
    return 'L0'

def apply(problem_id: str, work_dir: str = '.',
          level: str | None = None) -> list[str]:
    """Copy a problem's committed fixtures into *work_dir*, up to *level* (the
    problem's `minimize` rung by default). Flat layout (no L*/ subdirs) still
    works — it's treated as a single rung. Returns the relative paths provided."""
    src = fixture_dir(problem_id)
    if not src.is_dir():
        return []
    target = level or _minimize_level(problem_id)
    rungs = _LADDER[:_LADDER.index(target) + 1] if target in _LADDER else _LADDER
    provided: list[str] = []
    for f in sorted(src.rglob('*')):
        if not f.is_file():
            continue
        rel = f.relative_to(src)
        # A rung-prefixed file (L2/…, L3/…) is applied only when its rung is ≤ target;
        # an unprefixed file is always applied (flat fixtures, e.g. p6-rust today).
        if rel.parts[0] in _LADDER:
            if rel.parts[0] not in rungs:
                continue
            rel = Path(*rel.parts[1:])           # strip the rung dir
        dst = Path(work_dir) / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(f, dst)
        provided.append(str(rel))
    return provided
```

```python
# src/mu/dojo/runner.py — apply fixtures before the agent subprocess so the
# provided files are present when the writer starts (the measurement wiring).
from .. import fixtures
provided = fixtures.apply(problem_id, str(work))      # honors minimize level
if provided:
    print(f"Fixtures (L{fixtures._minimize_level(problem_id)}): {', '.join(provided)}")
```

A/B is then just the catalog field: set p10's `minimize` to `L2`, `L3`, `L4` across
runs and read where `k/4` (§A.4) jumps. **Honesty:** every reported pass carries
its rung; an L3 pass is never compared to the L0 baseline.

### A.3 Approach C — full-stack contract + a cross-stage type-ownership reflex

Two pieces. First, a deterministic L1 contract injected by the architect — extend
the `user_msg` / post-processing in `_run_architect_pass`
([agent.py](../../src/mu/agent.py):2009) for the detected full-stack stack so
`ARCHITECTURE.md` carries a fixed manifest + a single-owner type table:

```python
# src/mu/agent.py — after arch_text is written, for a multilayer dotnet+node goal.
if _is_multilayer(goal) and {'dotnet', 'node'} <= _goal_toolchains(goal):
    contract = (
        "\n## Type Ownership (one definition site each — do not redefine)\n"
        "- `Post` (Id:int, Title:string, Content:string) — backend/Models/Post.cs, public\n"
        "- `BlogContext : DbContext` — backend/Data/BlogContext.cs, public\n"
        "- the test project REFERENCES these via ProjectReference; it never redeclares them\n"
        "\n## Contract\n"
        "- route: GET /api/posts -> 200 JSON array of Post; seed one Title='Hello World'\n"
        "- test cmd: dotnet test backend.Tests && (cd frontend && npx vitest run)\n"
    )
    Path('ARCHITECTURE.md').write_text(arch_text + contract)
```

Second — and this is what actually kills CS0101/CS0053 — a deterministic guard
that runs before the integration gate. Follow the one-file-per-reflex pattern
([registry.py](../../src/mu/reflexes/registry.py) `_CATALOG`,
`src/mu/reflexes/csharp/`):

```python
# src/mu/reflexes/csharp/fix_csharp_cross_stage_duplicate_types.py
import re
from pathlib import Path
from ._common import *  # noqa: F401,F403

_DECL = re.compile(r'(?m)^\s*(?:public\s+|internal\s+)?(?:sealed\s+)?'
                   r'(?:class|record|struct)\s+(\w+)')

def fix_csharp_cross_stage_duplicate_types(project_dir: str) -> bool:
    """Across all .cs in the project, keep one definition of each type — the one
    under the backend source dir — and delete the duplicates the staged writer
    re-declared elsewhere (CS0101). General: any multi-project .NET layout that
    redefines a shared type across files. Never touches a uniquely-named type."""
    cs = [p for p in Path(project_dir).rglob('*.cs')
          if not any(s in p.parts for s in ('obj', 'bin'))]
    owners: dict[str, Path] = {}
    for f in sorted(cs):                       # backend/ sorts before *Tests/
        for name in _DECL.findall(f.read_text(errors='ignore')):
            owners.setdefault(name, f)         # first sort-order site = owner
    changed = False
    for f in cs:
        text = f.read_text(errors='ignore')
        for name in set(_DECL.findall(text)):
            if owners.get(name) != f:          # this file redefines an owned type
                text = _strip_type_block(text, name)   # remove the duplicate block
                changed = True
        if changed:
            f.write_text(text)
    return changed
```

Wire it into the staged-repair reapply (`apply_csharp_repair_reflexes`) and the
`_inter_stage_gate` reapply path, then catalog it under `'duplicate-declaration'`
in `registry.py` (the completeness test fails otherwise) and add an idempotency +
a "leaves a uniquely-named type alone" regression test. CS0053 gets a sibling
reflex that raises a type referenced by a `public` signature to `public`.

### A.4 The capability model as code: per-layer `q̂`, chain solve-prob, step selection

The metric is a direct read-out of §2.0. First, sample each run's per-layer
clears (the model's `q_{iℓ}` observations), parsed from the staged gate logs:

```python
# src/mu/dojo/measure.py
_P10_LAYERS = ('backend_build', 'backend_test', 'frontend_build', 'frontend_test')

def _layer_clears(session_dir: Path) -> dict[str, bool]:
    """One run's per-layer pass/fail — the model's q_{i,l} samples. Honest only
    if the gates reject vacuous passes (S1): a 'green' that ran no tests is not a
    clear."""
    text = '\n'.join(p.read_text(errors='ignore')
                     for p in (session_dir / 'logs').glob('*.log'))
    return {
        'backend_build':  'Build succeeded' in text and 'error CS' not in text,
        'backend_test':   bool(re.search(r'Passed!\s+-\s+Failed:\s+0', text)),
        'frontend_build': 'vite build' in text and 'error TS' not in text,
        'frontend_test':  bool(re.search(r'Test Files\s+\d+ passed', text)),
    }
```

Aggregate over the `N` runs into the model's quantities — per-layer `q̂`, the
**chain** solve-prob `∏ q̂` (vs. the measured pass rate), and the **bottleneck**
`argmin q̂` (Result 2: where the next step actually pays):

```python
def _capability_summary(runs: list[dict[str, bool]]) -> dict:
    n = len(runs) or 1
    q = {l: sum(r[l] for r in runs) / n for l in _P10_LAYERS}   # q̂_l = clears/N
    p_solve = math.prod(q.values())            # ∏ q̂_l  — series/chain system
    return {
        'q_per_layer':   q,
        'p_solve_model': p_solve,              # model P_i; compare to measured pass_rate
        'k_mean':        sum(q.values()),      # E[layers cleared] = Σ q̂_l (the old k/4)
        'bottleneck':    min(q, key=q.get),    # argmin q̂_l → the layer to attack next
    }
```

And the step-selection rule, straight from `∂P_i/∂q_{iℓ} = ∏_{ℓ'≠ℓ} q_{iℓ'}`
(Result 2) — it scores a candidate step by its *expected* contribution to the
chain, so a step on a layer whose siblings are still ≈0 scores ≈0 (why
backend-only scaffolding was rejected):

```python
def expected_solve_gain(q: dict[str, float], layer: str, dq: float) -> float:
    """Model's marginal value of a step that lifts `layer`'s q̂ by dq:
    ΔP_solve ≈ dq · ∏_{l'≠layer} q̂_{l'}. Pick the step maximizing this per unit
    cost (the depth-vs-breadth tradeoff, §2.0): on a 0/L problem it forces work
    onto the bottleneck; on a near-solved one it rewards the broadest β."""
    others = math.prod(qv for l, qv in q.items() if l != layer)
    return dq * others
```

`measure.run` already finds the session per run (`sessions.latest_since`); collect
`_layer_clears` across the `N` runs, emit `_capability_summary` in the
`--emit-json` block next to `pass_rate`, and rank candidate steps with
`expected_solve_gain`. These are the headline numbers for every arm in §2 and the
selector for §3's "build the lever the probe named."

### A.5 `capability.py` — the fitted model as one shared component (§2.0.1)

A thin layer over `observe.py` (Beta-Binomial `q̂`) and `reflexdb.py` (efficacy
`β`) that A, B, C, routing, and `practice` all call. Per-`(model, problem)` layer
stats in; `p_solve`, `bottleneck`, a step ranking, and a route decision out.

```python
# src/mu/capability.py — fitted capability model: one measurer/selector/router.
import math
from dataclasses import dataclass
from . import observe                         # Beta-Binomial Posterior (q̂ + CI)


@dataclass(frozen=True)
class LayerStat:
    clears: int                               # runs that cleared this layer
    n: int                                    # runs attempted
    @property
    def _post(self) -> "observe.Posterior":    # observe.beta_binomial -> Posterior(rate, lo, hi, n)
        return observe.beta_binomial(self.clears, self.n)
    @property
    def q(self) -> float:                      # smoothed q̂ (Beta-Binomial posterior mean)
        return self._post.rate
    @property
    def ci(self) -> tuple[float, float]:       # 95% credible interval — decide with fewer runs
        p = self._post
        return (p.lo, p.hi)


def p_solve(layers: dict[str, LayerStat]) -> float:
    """Chain solve-prob = ∏ q̂_l (series system) — the model's P_i."""
    return math.prod(s.q for s in layers.values())


def bottleneck(layers: dict[str, LayerStat]) -> str:
    """argmin_l q̂ — the layer the next step must target (Result 2)."""
    return min(layers, key=lambda l: layers[l].q)


def expected_solve_gain(layers: dict[str, LayerStat], layer: str, dq: float) -> float:
    """ΔP_solve ≈ dq · ∏_{l'≠layer} q̂  — a step's marginal value via the chain."""
    others = math.prod(s.q for l, s in layers.items() if l != layer)
    return dq * others


def route(layers: dict[str, LayerStat], eps: float = 0.02) -> bool:
    """Skip the (model, problem) when p_solve < eps — the layer-level generalization
    of fixtures.should_skip, shared across all three LLM models."""
    return p_solve(layers) < eps


@dataclass(frozen=True)
class Step:
    name: str
    layer: str            # the layer it lifts
    beta: float           # efficacy Δ (partial-pooled across models; reflexdb)
    cost: float           # median added tokens/iters


def rank_steps(layers: dict[str, LayerStat], steps: list[Step]) -> list[tuple]:
    """Order candidate steps by expected ΔP_solve per unit cost. headroom = β·(1−q̂)
    is the logistic gain on the target layer; the chain factor routes it to the
    bottleneck on a 0/L problem and to the broadest β on a near-solved one
    (depth-vs-breadth, §2.0)."""
    scored = []
    for s in steps:
        dq = s.beta * (1 - layers[s.layer].q)
        gain = expected_solve_gain(layers, s.layer, dq)
        scored.append((gain / max(s.cost, 1e-9), s.name, s.layer, gain))
    return sorted(scored, reverse=True)
```

Consumers: `measure.py` builds `{layer: LayerStat}` from `_layer_clears`;
**A** reads `bottleneck`/`expected_solve_gain` to scaffold only where it pays;
**C** registers its reflex as a `Step` and is ranked by `rank_steps`;
**B** supplies the `δ`-jumps that calibrate the `LayerStat`s; the `practice` loop
and `dojo run --route` call `route` for every model. One object, every consumer.

---

## 7. Out of scope: constrained decoding

Grammar-/type-constrained decoding (mask tokens that break syntax or static
types) would make structure deterministic at generation time — the most powerful
"determinism" lever in the literature. It is **not feasible in mu today**: mu
drives models through LM Studio's OpenAI-compatible *chat* endpoint, which exposes
no per-token logit mask. Pursuing it would mean a different inference path
(e.g. llama.cpp grammars) — a larger architectural change than this report's
scope, recorded here as the long-horizon option if mu ever takes token-level
control of generation.

## 8. References

- [tw]: Thoughtworks — *Spec-driven development* (2025). https://www.thoughtworks.com/en-us/insights/blog/agile-engineering-practices/spec-driven-development-unpacking-2025-new-engineering-practices
- [ghspec]: GitHub — *Spec-driven development with AI (spec-kit)*. https://github.blog/ai-and-ml/generative-ai/spec-driven-development-with-ai-get-started-with-a-new-open-source-toolkit/
- [sdd]: *Spec-Driven Development: From Code to Contract in the Age of AI Coding Assistants*, arXiv:2602.00180. https://arxiv.org/abs/2602.00180
- [skel]: *Skeleton-Guided-Translation: A Benchmarking Framework for Code Repository Translation*, arXiv:2501.16050. https://arxiv.org/pdf/2501.16050
- [tdd]: *A Test-Driven-Development Benchmark for LLM Code Generation*, arXiv:2505.09027. https://arxiv.org/pdf/2505.09027
- [decay]: *Constraint decay: The Fragility of LLM Agents in Backend Code Generation*, arXiv:2605.06445. https://arxiv.org/html/2605.06445
- [fail]: *Where LLM Agents Fail and How They Can Learn From Failures*, arXiv:2509.25370. https://arxiv.org/abs/2509.25370
- [casc]: *Hallucination Cascade: Error Propagation in Multi-Agent LLM Systems*, arXiv:2606.07937. https://arxiv.org/html/2606.07937
- Constrained/grammar decoding (§7): *Correctness-Guaranteed Code Generation via Constrained Decoding*, arXiv:2508.15866; *Grammar-Constrained Decoding for Structured NLP Tasks*, arXiv:2305.13971.
