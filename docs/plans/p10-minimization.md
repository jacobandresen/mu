# Plan: minimizing & de-risking the p10 problem space

**Objective:** solve more of the ten dojo problems — formally, raise
$E[N_{\text{solved}}] = \sum_i P_i$ (stretch $P_{\text{all}} = \prod_i P_i$).
**p10-dotnet-vue-blog** is the *worked example* — the dojo's one persistently
0-pass problem, because it exercises every mechanism — but the capability model
(§1), the `reduce()` loop (§2.1), and the broad levers (honest gates S1, the
cross-stage reflex S2) are built to lift the **whole set**, and §0.1 shows the
highest-EV targets are usually **not** p10.

**The binding constraint** is a principle (§0.2): **mu must not rely on fixtures
or pregenerated code.** Anything we hand the agent moves p10's *number* without
making the *agent* better. Status: **proposed / in progress** (§4.3 is a live
checklist). Written 2026-06-19, trimmed 2026-06-20.

---

## 0. Objective and principle

### 0.1 Optimise `E[N_solved]` over the set, not `P_10` in isolation

The capability model (§1) gives the marginal value of a step on problem $i$,
layer $\ell$:

$$\frac{\partial E}{\partial(\text{step})} \;\propto\; \beta \cdot \underbrace{q_{i\ell}(1-q_{i\ell})}_{\text{logistic headroom}} \cdot \underbrace{\prod_{\ell'\neq\ell} q_{i\ell'}}_{\text{chain factor}}$$

— logistic headroom (Result 3) **times** the chain factor (Result 2). The
consequence: for **p10** every layer sits at $q\approx0$, so *both* factors are
$\approx 0$ — a step there buys almost nothing per unit cost. For a **mid-tier**
problem at $q\approx0.5$ with healthy siblings, $q(1-q)=0.25$ and $\prod\approx1$
— the *same* $\beta$ buys far more solved problems. **To solve more of the ten,
the steep mid-tier problems and the broad levers dominate the hardest problem.**

Current measured rates (recent archive; p7 $\approx$80% post the false-pass fix):

| solved ✓ ($\ge$90%) | mid-tier (most marginal EV) | frontier |
|---|---|---|
| p1, p3, p6 (100%), p9 (94%) | **p8 42%, p7 ~80%, p4 66%, p2 71%, p5 89%** | **p10 0%** |

So the program that maximises `E[N_solved]` is a **portfolio**: (1) **broad levers
first** — a general reflex/skill lifts several problems at once (S1, S2, the
`reduce()` loop); (2) **then the steep mid-tier** — lifting p8 42$\to$70% adds $\approx$0.28
to `E[N_solved]` cheaply, more than dragging p10 0$\to$>0 at high cost; (3) **p10 as
the frontier** — invest only via levers that also help others, until stacked
reductions drag its `q` into the steep region. The selector (§A.5 `rank_portfolio`)
ranks every candidate by its *summed* expected gain across the problems it covers,
over **all ten**, not p10 alone.

### 0.2 The principle: no fixtures, no pregenerated code

Handing mu correct files (a committed fixture) or a copied skeleton (a vendored
template) can make p10 *pass* without teaching mu anything. Per the codebase's own
rule a fixture is "correct boilerplate given to the model, not an answer key" — a
**measurement device, external to the agent.** The capability model makes the cost
exact: external code lowers $\delta_{i\ell}$ for one problem at a declared level
but adds no transferable $\beta$ and does not raise $\theta$ — it buys $P_i$
without raising ability (§1.3, tradeoff 1).

So the durable win is mu reducing its **own** problem space: self-scaffolding by
*invoking* the toolchain's own generator, writing and then honouring its own
contract, and building in vertical slices it generates itself.

> **The substep clarification.** "No pregenerated code" forbids *seeding the agent
> with code it did not generate.* It does **not** forbid a later substep building
> on an earlier one. When a reduction is split into slices, it is expected and
> correct that **step 2 relies on the code mu generated in step 1** — that *is* the
> vertical-slice method (skeleton $\to$ one gated layer green $\to$ expand on it). The line
> is provenance: code mu wrote in a previous slice is fair game; code we authored
> and dropped into its workspace is not.

This principle is the gate on every lever in §2: Approach C (contract) and S2
(reflex) are general capability that mu owns; Approach B (committed fixtures) is a
**diagnostic probe only**, shipping no fixtures as product; Approach A is
acceptable only in the form where **mu runs `dotnet new` / `npm create vite`
itself** (tool-generated, mu's own output) — a copied vendored skeleton is the
part that conflicts, kept only as a last-resort offline fallback.

### 0.3 Why p10 is the open problem

p10 asks for a coordinated two-project full stack in one shot: an ASP.NET Core
minimal API with EF Core/SQLite, a seeded `Post` model, `GET /api/posts`, an
xUnit `WebApplicationFactory` integration test, *plus* a Vue 3 + Vite + TS
frontend with a Vitest fetch-mock test, wired by one Makefile. It runs in
architect (staged) mode ([`_detect_stages`](../../src/mu/agent.py)).

Measured (run 7, qwen2.5-coder-7b, ctx 6000): **0/12**, median 6 repair iters,
~33k prompt tokens/run — the heaviest, least reliable problem in the set.

| Error | Count | Class |
|---|---|---|
| CS0101 duplicate type in global namespace | $\times$14 | cross-stage **coordination** (types redefined across files) |
| MSB1003 no project/solution at the test dir | $\times$8 | **structure** (where `dotnet test` runs) |
| CS0053 inconsistent accessibility (public API exposes internal EF type) | $\times$8 | **coordination** (type-ownership / visibility) |

**The decisive prior: structure is probably *not* the binding constraint.**
`src/mu/scaffold.py` exists but is the detection+recipe core only, **unwired**
(commit `48fa0c8`). A later branch (project memory `project-scaffolding-impl`, not
merged here) wired it per-`run`, fixed an ordering bug so it actually fired, and
ran a pre-registered A/B whose verdict was **DROP**:

> p10 A/B (scaffold confirmed firing): baseline **0/8** vs treatment **0/8** — no
> movement, and repair-iters *rose* 0.8 $\to$ 2.2. Backend scaffolding fixes
> MSB1003/CS0017 **but not p10's real ceiling**: the frontend, the
> WebApplicationFactory integration test, and multi-project coordination.

Treat this as a **strong working hypothesis**, not in-tree fact: any new proposal
must be judged on whether it attacks **coordination** (CS0101/CS0053, $\times$22 combined)
and the **frontend/integration logic**, not just structure.

### 0.4 What the 2026 literature says

The external picture lines the levers up almost exactly:

- **Spec-/contract-driven development** — a structured spec as source of truth,
  planning separated from implementation, measurably less hallucination
  ([Thoughtworks 2025][tw], [spec-kit][ghspec], [2602.00180][sdd]). $\to$ contract (C).
- **Skeleton/template-guided generation** — ship a target skeleton and have the
  model fill the dynamic parts ([2501.16050][skel]). $\to$ self-scaffold (A) / the
  vertical-slice skeleton.
- **TDD-style pinning** — the test-as-contract is "a fundamental determinant of
  success"; ~40% of agent code still fails the reference even when it runs
  ([2505.09027][tdd]). $\to$ the B-probe's L3 rung, and S5 test skills.
- **Cascade control / atomic decomposition** — "error propagation is the primary
  bottleneck in agent reliability"; decompose into the smallest gated subtasks so
  an early mistake can't compound ([2605.06445][decay], [2509.25370][fail]).
  This is *exactly* p10's repair-oscillation mode. $\to$ S2 (independent gates) and the
  `reduce()` loop's vertical slices.

mu's own minimization ladder ([DOJO.md](../../DOJO.md)) is the local name for this:
**L0 open $\to$ L1 contract $\to$ L2 scaffold $\to$ L3 test-pinned $\to$ L4 fill-in.**

---

## 1. The capability model

### 1.1 The logistic chain

mu's staged, gated architecture gives the model for free. A problem $i$ is
verified by $L_i$ independent gates — its **layers**. p10 has $L=4$ (backend
build, backend test, frontend build, frontend test); a trivial problem — the
hello-world **p1** (`p1-helloworld`) — has $L=1$, so it clears in a single step.
mu solves $i$ iff it clears **every** layer — a *series system* in reliability
terms.

Layer $(i,\ell)$ clears with probability (standard IRT "ability − difficulty"):

$$q_{i\ell} = \sigma(z_{i\ell}), \qquad \sigma(x) = \frac{1}{1+e^{-x}}$$

$$z_{i\ell} = \theta\, a_\ell \;-\; \delta_{i\ell} \;+\; \sum_k \beta_k\, x_{ki\ell} \;-\; \gamma\, V_{i\ell}$$

| symbol | meaning | moved by |
|---|---|---|
| $\theta$ | model ability (per model / toolchain) | model choice / routing |
| $\delta_{i\ell}$ | intrinsic difficulty / *size* of subproblem at layer $\ell$ | **problem-space reduction** (self-scaffold, contract, slicing) |
| $\beta_k \ge 0$ | strength of step $k$ | reflexes, skills |
| $x_{ki\ell}$ | coverage: does step $k$ touch layer $(i,\ell)$ (its **breadth**) | generality of the step |
| $\gamma V_{i\ell}$ | variance penalty (degeneration, planner noise) | guards, seed, prompt-cache |
| $a_\ell$ | layer discrimination | (structural) |

**Objective.** $P_i = \prod_\ell q_{i\ell}$; $\;E[N_{\text{solved}}] = \sum_i P_i$;
$\;P_{\text{all}} = \prod_i P_i$. All three are strictly increasing in every
$q_{i\ell}$.

### 1.2 Three results

**Result 1 — each step provably raises the likelihood (monotonicity).** $z$
increases in $\theta$ and each $\beta_k$ (with $x\ge0$), decreases in $\delta$ and
$V$; $\sigma$ is strictly increasing. So any step that raises $\theta$, adds a
$\beta_k\ge0$, lowers a $\delta$, or lowers a $V$ — *without lowering another
layer's $z$* — strictly increases the affected $q_{i\ell}$, hence $P_i$,
$E[N_{\text{solved}}]$, $P_{\text{all}}$. That is **no-regret**: a step is no-regret
iff $\Delta z_{j\ell'}\ge0$ everywhere.

**Result 2 — the chain makes the *weakest* layer decisive (and explains the
dropped scaffolder).**

$$\frac{\partial P_i}{\partial q_{i\ell}} = \prod_{\ell'\neq\ell} q_{i\ell'}, \qquad \log P_i = \sum_\ell \log q_{i\ell}$$

The marginal value of improving layer $\ell$ is the **product of the other
layers' pass probabilities** — so if any sibling $\approx0$, improving $\ell$
barely moves $P_i$. For p10 (all four layers low) raising only the backend layer
leaves $P_i\approx0$: precisely the measured 0$\to$0 of backend-only scaffolding. For
a 0/L problem the binding move is to lift the **minimum** layer
($\max\min_\ell q_{i\ell}$) until every factor exceeds 0; $\arg\min_\ell \hat q_{i\ell}$
names the layer to attack next.

**Result 3 — reduction has the highest leverage when the model is weak (sigmoid
steepness).**

$$\frac{dq}{dz} = \sigma(z)\,(1-\sigma(z)) \quad\text{peaks at } z=0\ (q=0.5),\ \text{tiny in the tails.}$$

A layer at $q\approx0$ sits deep in the negative tail, so a *single* step barely
moves it — you must **stack** steps ($\sum\beta$, $\Delta\delta$) to drag $z$ from
very negative toward 0 before returns appear. Progress is invisible in binary pass
($z:-5\to-2$, $q$ still $\approx0$) yet visible in a finer metric — the formal case
for $k/4$ (§1.5). And: when $\theta$ is small and $\delta$ large (a weak local
model on a big subproblem — **mu's regime**), lowering $\delta$ gives the biggest
$dq$. That is the mathematical reason mu's edge is problem-space reduction +
reflexes, not a bigger model.

### 1.3 Tradeoffs (read straight off the model)

1. **Reduction vs. capability — the honesty tradeoff (this is §0.2 in math).**
   External fixtures lower $\delta_{i\ell}$ at a declared level but add no
   transferable $\beta$ and don't raise $\theta$. The **L-level *is* the amount of
   $\delta$ removed externally**; a pass at lowered $\delta\neq$ a pass at full
   $\delta$. mu's *own* reduction lowers $\delta$ through a general mechanism — a
   real capability gain.
2. **Generality vs. risk.** A step with $\beta>0$ on its target but $\beta<0$
   elsewhere (overfit, wrong-deletion) lowers some $q$. Ship iff net
   $\Delta E[N_{\text{solved}}] = \sum_{\text{helped}} - \sum_{\text{hurt}} > 0$ and no
   control layer regresses.
3. **Variance vs. cost.** Lowering $V$ raises $q$ but costs tokens; $\sigma$
   saturates as $q\to1$. Ship while $\Delta q\cdot(\partial P/\partial q)/\Delta T >$ threshold.
4. **Depth vs. breadth.** For a 0/L problem, concentrate on the bottleneck layer
   (Result 2); for a near-solved problem, spread to the broadest $\beta$ (largest
   $\sum_i x_{ki\ell}$).
5. **$\theta$ vs. $(\delta,\beta)$.** A bigger model ($\theta\uparrow$ uniform, but
   swap-bound on 8 GB) vs. reduction+reflexes ($\delta\downarrow$, $\beta\uparrow$,
   targeted, free locally). Result 3 says the latter dominates in mu's regime.

**Estimable from what mu already logs** (so the model is a *fit*, not an
abstraction): $\hat q_{i\ell}=$ clears/$N$ per layer (honest only if S1 rejects
vacuous passes); $\theta\approx$ KB `competence_by_toolchain`; $\beta\approx$ a
reflex's `efficacy` $\Delta$; $V\approx$ stochasticity $1-\text{modal}/N$; the
Beta-Binomial `observe.Posterior` gives $\hat q$ with a CI and `sz5_gate` tests
$\Delta q$.

### 1.4 Fitting it: the hierarchical logistic (one shared component)

The model earns its keep only if it can be *fitted from dojo data* and *queried
through one interface* by every lever. Both fall out of the parameterization. Pool
every $(\text{model }m,\text{ problem }i,\text{ layer }\ell,\text{ run})$ outcome
and fit a **hierarchical logistic** with partial pooling:

```text
# Hierarchical logistic fit of per-layer success  q = σ(z)
# data: one row per (model m, problem i, layer ℓ, run), outcome y ∈ {0,1}

# ---- partial-pooling priors (the "hierarchical" part) ----
θ[m]        ~ Normal(0, 1)                  # per-model ability: granite-3b, qwen-3b, qwen-7b
β̄[k]        ~ Normal(0, 1)                  # global effect of step k (reflex / reduce-move)
β[k, m]     ~ Normal(β̄[k], τ²)              # per-model deviation; τ small ⇒ step k is GENERAL
δ_kind[c]   ~ Normal(0, 1)                  # difficulty shared by layer-kind c ∈ {build, test}
δ[i, ℓ]     ~ Normal(δ_kind[kind(ℓ)], σδ²)  # per (problem, layer); a NEW problem borrows its kind

# ---- likelihood ----
for row (m, i, ℓ, y):
    z = θ[m]·a[ℓ] − δ[i, ℓ] + Σ_k β[k, m]·x[k, i, ℓ] − γ·V[i, ℓ]
    y ~ Bernoulli(σ(z))

# ---- read-outs every consumer queries (see capability.py) ----
q̂[m, i, ℓ]  = σ( E[z | data] )              # per-layer pass prob, with a CI
p_solve     = ∏_ℓ q̂[m, i, ℓ]                # chain / series system  → capability.p_solve
bottleneck  = argmin_ℓ q̂[m, i, ℓ]           # weakest link           → capability.bottleneck
gain(ℓ, dq) = dq · ∏_{ℓ'≠ℓ} q̂[m, i, ℓ']     # marginal value (Result 2) → expected_solve_gain
```

Partial pooling is what makes the thin data usable: a reflex's effect measured on
qwen *informs* its effect on granite (whose data is sparse); a truly general
reflex shows a tight $\beta$ across models, one that only rescues a weak model
shows a per-model deviation.

**Practical estimator (not from-scratch MCMC).** 10 problems $\times$ 1–4 layers $\times$ 3
models is thin for a joint fit with dozens of $\beta$. The shipped estimator
collapses the hierarchy onto machinery mu already has:

1. **$\hat q$ per $(m,i,\ell)$** by Beta-Binomial smoothing — exactly
   `observe.Posterior` (needs S1, or $\hat q$ is biased high).
2. **$\beta_k$** from the **ablation/efficacy $\Delta$** mu already computes
   (`efficacy_run`, `sz5_gate`), pooled over the layers it covers ($x$ from
   `firings.jsonl`).
3. **$\delta$** from the B-probe: the jump in $\hat q$ between rung $L(k)$ and
   $L(k{+}1)$ *is* an estimate of that layer's $\delta$ contribution. **B is
   literally the experiment that identifies $\delta$** — its only honest role.

**One component, three consumers — already shipped** as
[`src/mu/capability.py`](../../src/mu/capability.py) (a thin layer over
`observe.py`/`reflexdb.py`): `p_solve`, `bottleneck`, `expected_solve_gain`,
`route`, `e_solved`, `portfolio_gain`, `rank_portfolio` (§A.5). The *same* object
measures the agent, ranks the next step, and routes the weak models — every lever
and the `practice` loop call it, instead of each growing its own analysis.

### 1.5 The metric: per-layer $\hat q$ and the board ($k/4$)

Binary p10 pass-rate is **0** and cannot rank three interventions that all start
from 0 (their gains hide in the negative tail, Result 3). The comparison uses
**graded, continuous signal** — the per-layer $\hat q$ and chain solve-prob — via
the existing efficacy machinery (`observe.Posterior`, `sz5_gate`, `efficacy_run`).

Four checkpoints the harness reads from stage logs:

1. **Backend builds** — no CS/MSB errors from `dotnet build`.
2. **Backend+integration test passes** — `dotnet test` green (WebApplicationFactory
   `GET /api/posts` $\to$ "Hello World").
3. **Frontend builds / type-checks** — `vite build` / `tsc` clean.
4. **Frontend Vitest passes** — mocked-fetch render assertion green.

`p10 pass` $\Leftrightarrow$ all four. The headline metric is **mean $k/4$ reached per run** — a
continuous score that *moves* while binary pass is pinned at 0, and that
**localizes** where each lever helps. The **board** (§A.5) generalizes this to all
ten: per-layer $\hat q$, per-problem `p_solve`, the bottleneck, and
$E[N_{\text{solved}}]$ with a CI.

---

## 2. The levers, ranked by the principle

Three external levers map onto the ladder; the principle (§0.2) decides which
become product:

| Lever | Ladder | Mechanism | Relies on pregenerated code? | Honesty verdict |
|---|---|---|---|---|
| **A** scaffold | L2 | stage-aware skeleton | **only if it copies a vendored blob** — fine if mu *runs* `dotnet new`/`npm create` | conditional (structure must bind) |
| **B** fixtures | L2$\to$L4 | committed correct boilerplate per rung | **yes — by construction** | **diagnostic probe only, never product** |
| **C** contract | L1 | declarative manifest + single-owner type ledger | **no** — mu writes every file | **product** |

So the real deliverables are the *general, no-pregenerated-code* mechanisms:
**S2** (cross-stage type reflex), **C** (the contract), **S5**
(WebApplicationFactory + Vitest test-authoring skills), and **A** *only* in its
tool-invoked form if structure turns out to bind. **B is a measurement device**:
it localizes the ceiling cheaply so the capability work is aimed correctly, and
its fixtures persist only as a labelled-L-level regression signal.

### 2.1 The product: mu's own reduce-then-solve loop

The levers above are not separate features — they are the **moves of one
capability mu should own**: a `reduce()` pass that runs before the writer on any
goal `detect_complexity` flags as hard/multi-layer.

> **Easy problems stay one-shot (the p1 expectation).** `reduce()` is
> **complexity-gated**: a trivial, single-layer goal ($L=1$) — the canonical case is
> **p1** (`p1-helloworld`), one file, one gate — is *not* flagged, skips reduction
> entirely, and is **solved fast in a single step**: no self-scaffold, no contract,
> no slicing, no extra round-trips. The decomposition machinery is reserved for the
> hard, multi-layer goals (p10); it must never add latency or steps to hello-world or
> any easy/control problem. Enforced by I1 (flags-off $\Rightarrow$ byte-identical) and
> I4 (no control regression on p1/p2/p5/p6).

| External lever (today) | Internalized as a mu capability |
|---|---|
| A — we scaffold from a template | **mu self-scaffolds**: detects the stack and *invokes the toolchain's own generator* (`dotnet new`, `npm create vite`) — mu's own output, no copied blob |
| C — we pin a contract | **mu writes its contract first**: manifest + single-owner type ledger + per-layer test command, then holds itself to it (extends the architect) |
| B — we hand it fixtures | **mu builds in vertical slices**: skeleton $\to$ one layer green at a gate $\to$ expand. The *spirit* of the staircase (smallest verifiable core first) with **no answer-keys** — and each slice builds on the code the previous slice generated (§0.2). The only honest internalization of B |
| (the cascade literature) | **mu decomposes** the goal into the smallest independently-gated subtasks and stops an error before it compounds |

The product is a general **`reduce()` stage**: detect $\to$ self-scaffold $\to$ contract +
type-ledger $\to$ vertical-slice plan with a gate per slice $\to$ writer fills the smallest
next slice, *each slice resting on the previous slice's verified output.*
`ground_plan` and architect mode are the embryonic version; the work is to
generalize and *train* it — the `practice` loop + competence/KB are the training
signal, so the skill improves with data instead of being hand-tuned per problem.

This relocates the harness's job: the dojo no longer *applies* minimization (except
B as a one-off probe) — it **measures and trains** mu's own reduction. The agent
owns making the problem small; the harness only scores how well it does it.

### 2.2 The no-regret backlog (S1–S5)

Prerequisites for *every* lever and for comparing them; the first two carry their
own weight even if every lever is later dropped:

1. **S1 — Honest per-layer gates (do first).** $k/4$ is only trustworthy if each
   gate detects a *vacuous* pass. `make` is covered (`_make_vacuous`); extend the
   family to p10's real gates: `dotnet test` (0 tests, or "Build FAILED" with exit
   0) and `vitest` ("No test files found"). Without S1, every lever is scored
   against a lying instrument. Same class as the p7 false-pass fix — **no-regret**.
2. **S2 — Cross-stage type-ownership guard (highest leverage).** CS0101+CS0053 are
   $\times$22 of p10's errors. A deterministic general guard (keep the backend-owned
   definition, delete cross-stage duplicates $\to$ CS0101; raise a type behind a
   `public` signature $\to$ CS0053) is needed under every lever and **also helps p4** —
   a general multi-project-.NET reflex, **no-regret**.
3. **S3 — One reconciliation routine.** Generalize `agent.py:678` into a single
   "these paths are fixed; the model owns the rest and may neither rewrite nor
   redeclare them" contract that A, B, and C all call with a different file set.
4. **S4 — One detector + level bookkeeping.** A shared `is_fullstack_dotnet_vue`
   capability check and a `meta.json.minimize`/`scaffold` record, so every reported
   pass carries its rung and no run is silently compared across levels.
5. **S5 — Test-authoring skills.** No *structural* lever reaches the model's
   ceiling: authoring a correct `WebApplicationFactory` integration test and a
   correct Vitest fetch-mock. All levers top out one layer short without these (B
   only crosses it by *pinning* the tests at L3 — the diagnostic that tells you
   whether S5 is worth writing).
6. **S6 — Bottom-up dependency build order (general, no-regret).** Build the plan
   smallest-part-first: a module *called by* another is written before its caller,
   manifests first, tests last — the cascade-control lever (§0.4) that stops an
   early mistake from compounding, and the design criterion behind the `reduce()`
   loop's vertical slices (§2.1). Unlike the structural levers it is **not** p10-
   specific: it reorders *any* multi-file plan, so by the portfolio argument (§0.1)
   it covers the steep mid-tier (p2/p4/p7/p8) as well as p10's coordination layer.
   Shipped flag-gated (`MU_BUILD_ORDER`, `plan.build_rank`/`build_order`/
   `reorder_plan`); the remaining slices are the **incremental Makefile** (woven per
   step, never a trailing task) and **per-slice test gating** (build+test each module
   as it lands). No-regret: off ⇒ byte-identical (I1).

### 2.3 Decision rubric (pre-registered, weighted)

Per arm, $\ge$15 fresh-plan runs (`mu dojo measure p10 -n 15`); **honesty is a gate,
not a weight.**

| Axis | Weight | What wins |
|---|---|---|
| Lifts p10 (pass-rate CI lower bound > 0, or mean $k/4$ $\uparrow$ with CI$\not\ni$0) | 0.35 | the headline |
| Determinism (stochasticity $\downarrow$) | 0.20 | a tighter instrument |
| Cost (repair-iters & tokens $\downarrow$, not $\uparrow$) | 0.15 | cheaper runs |
| Generality / product value (helps novel goals, capability-keyed) | 0.20 | A, C |
| Implementation + maintenance cost | 0.10 | B |
| **Honesty gate** (label L-level; controls p1/p2/p5/p6 $\Delta$ CI $\ni$ 0) | gate | any arm that regresses a control or misreports its level is disqualified |

Continuous metrics ($k/4$, iters, tokens) decide with far fewer runs than binary
pass/fail — the explicit reason to build §1.5.

---

## 3. Recommendation: the explicit build order

The principle (§0.2): only a **general capability** counts; a fixture pass yields
**zero** capability value, so Approach B earns its place *only* as the probe that
names which capability to build. Build in this exact order — every item is a
fully-specified step in §4.3, named here with its KEEP/proceed gate.

**A. Do now — no branch, no decision needed (no-regret; runs regardless of the probe):**

| # | Step | File(s) | Produces | Proceed / KEEP gate |
|---|---|---|---|---|
| 1 | **0.1 S1 honest gates** | `src/mu/agent.py` | a gate that rejects a vacuous pass on every toolchain | 0 genuine archived passes reclassified |
| 2 | **0.2 whole-set board** (`mu dojo board`) | `src/mu/dojo/measure.py`, `src/mu/dojo/cli.py` | per-layer $\hat q$, `p_solve`, `bottleneck`, `e_solved` over all ten | set-level self-consistency holds |
| 3 | **0.3 S2 cross-stage type reflex** $\leftarrow$ *the headline shippable* | `src/mu/reflexes/csharp/`, `registry.py`, `agent.py` | a CS0101/CS0053 fixer (helps p10 **and** p4) | backend-layer $\hat q$ $\Delta$ CI lo **> 0** $\wedge$ p4 not regressed |
| 4 | **0.4 S3/S4 reconcile + detector + level record** | `src/mu/agent.py`, `src/mu/scaffold.py` | one mark-provided-done routine; `meta.json.minimize` | byte-identical with flags off |
| 5 | **0.5 L0 baseline** | *(run only — no file)* | the reference board every later arm diffs against | records, does not gate |

**B. Then probe — run-once, instrumental, then set aside:**

| # | Step | File(s) | Produces |
|---|---|---|---|
| 6 | **1.1–1.4 Approach B $\delta$-staircase** | `dojo/fixtures/p10/`, `src/mu/fixtures.py`, `src/mu/dojo/runner.py` | the rung (L2 / L3 / L4) at which mean $k/4$ jumps $\to$ the binding layer |

**C. Then build *exactly one* lever, selected by the probe (decision gate, Step 1.4):**

| Probe result | Build | File(s) | Because |
|---|---|---|---|
| jump at **L2** (a build layer) | **2a Approach A** — mu self-scaffolds via `dotnet new` / `npm create vite` | `src/mu/scaffold.py`, `src/mu/agent.py` | structure binds |
| jump only at **L3** (a test layer) | **2b Approach C** (contract) **+ S5** (test-authoring skills) | `src/mu/agent.py`, `src/mu/reflexes/csharp/`, `src/mu/reflexes/javascript/` | coordination + test logic bind |
| no jump until **L4** | **nothing** — `route()` p10 (`MU_ROUTE`); keep the L3 fixture as a labelled regression signal | *(route only — no file)* | irreducible model ceiling |

7. **2c — calibrate** the model (predicted vs measured $\Delta$) *before* declaring the
   lever shipped.
8. **Phase 3 — record & generalize**; promote any KEEP'd general capability toward
   the product path.

**Stop rule:** §4.2 step 7 — halt when no candidate clears the cost threshold.

Two justifications. The mental check for each item: *would this help mu on a novel
full-stack goal it has never seen?* S2/C/S5/A pass; B does not — which is exactly
why B is a probe, not the product. And front-loading C or A is dominated (most cost
to learn the least, and A already failed once, §0.3); front-loading B *as if it
were the answer* makes the number move without making mu better — the error the
principle rules out ([AGENTS.md](../../AGENTS.md) §0, memory
`project-false-pass-gate`, `feedback-honest-dojo`). B's artifacts still
**compose**: its `L2` tree is the offline reference A validates against and the
golden reference C's guard checks — so even when B leads to A or C, nothing is wasted.

---

## 4. Implementation: a provable, whole-set loop

The plan is **not** "fix p10." It is a loop that **provably raises
$E[N_{\text{solved}}]$ across all ten**, one shipped step at a time, with p10 handled
as whatever candidates happen to cover it (rarely the first target, §0.1).

### 4.1 Invariants every step preserves

Non-negotiable; each becomes a test so a violation fails CI, not a live run.

- **I1 Default-off.** Any agent-affecting change sits behind a flag defaulting off;
  with all flags off the run is **byte-identical** to today (`test_*_noop`).
- **I2 Offline.** No step adds a hard network dependency; an online tier degrades to
  a fallback or baseline.
- **I3 Honest level.** Every recorded pass carries its L-level in `meta.json`; no
  statistic compares across levels.
- **I4 No control regression.** p1/p2/p5/p6 pass-rate $\Delta$ has a 95% CI lower bound
  $\ge$ −$\varepsilon$ ($\varepsilon$ = 0.05). Any breach is reverted.
- **I5 Idempotent + graceful.** Every reflex/scaffold op is idempotent and never
  raises into the agent loop — a failure degrades to baseline.
- **I6 Pre-registration.** The KEEP/DROP statistic, N, and threshold are written
  *before* the run.
- **I7 No external code.** No step seeds the agent with code it did not generate
  (§0.2). A reduction's later slice **may** build on an earlier slice's *generated*
  output; it may **not** depend on committed boilerplate or a copied skeleton. (B's
  fixtures violate this by design — that is why B is a probe, scored under its own
  L-level, never shipped on the L0 product path.)

Each step names its **target file(s) in the heading**, then is specified
**Files $\to$ Build $\to$ Tests $\to$ Accept $\to$ Measure $\to$ Gate $\to$ Rollback** — where
**Build** is an ordered, imperative checklist and every action says which file it
edits.

### 4.2 The loop and its proof obligation

**Proof obligation.** A candidate step $k$ is **shipped** iff the dojo measurement
shows, via the existing Beta-Binomial / `sz5_gate` machinery:

- **(P1) it raises the set:** $\Delta E[N_{\text{solved}}]$ has a 95% CI lower bound
  **> 0**; and
- **(P2) it regresses nothing:** every problem's pass-rate $\Delta$ has a CI lower bound
  **$\ge$ −$\varepsilon$** ($\varepsilon$ = 0.05) — controls p1/p2/p5/p6 *and* every covered problem.

By Result 1, a step meeting **P1 $\wedge$ P2** strictly increases $E[N_{\text{solved}}]$.
So the shipped sequence makes $E[N_{\text{solved}}]$ a **monotone-increasing ledger**:
every KEEP is a *proven* gain across the set; every step that cannot prove P1$\wedge$P2 is
reverted.

**The loop (each pass ships $\le$1 proven step):**

1. **Measure the board** — all ten at N (§A.5): per-layer $\hat q$, `p_solve`,
   $E[N_{\text{solved}}]$ with CIs. S1 makes $\hat q$ unbiased.
2. **Generate candidates** — from the board's bottleneck layers ($\arg\min\hat q$)
   and the KB's recurring *cross-problem* error classes; each carries an estimated
   $\beta$ and coverage $x$.
3. **Rank by `portfolio_gain`** = $\sum_i\sum_\ell$ expected_solve_gain over covered
   $(i,\ell)$, per unit cost. By Results 2–3 this **automatically prefers a broad
   lever on steep mid-tier problems** over a narrow p10-only lever.
4. **Implement** the top candidate (general reflex / skill / `reduce()` move), gated
   off, with unit tests and the §4.1 invariants.
5. **Prove it** — A/B (ablation) over covered problems + controls at the §4.5 power
   N. **KEEP iff P1$\wedge$P2**; else **revert**.
6. **Refit & recompute** the board; append the proven $\Delta$ to the ledger.
7. **Repeat from 2. Stop** when no candidate clears the cost threshold — guaranteed
   to terminate because steepness (Result 3) drives marginal gains down as
   $\hat q\to1$.

### 4.3 The steps — live checklist

> **Ablation results live in [`docs/ablations.md`](../ablations.md)** — the canonical
> log of every lever tried, its A/B numbers, and its verdict (SHIPPED / UNDER TEST /
> PARKED / DROPPED). This checklist tracks *work items*; that file is the *results
> ledger*. Don't duplicate verdict prose here — link to it.

**This section is a live tracker** — tick `- [ ]` $\to$ `- [x]` on GitHub as each
item lands. Each step is a milestone checkbox carrying its **target file(s)**; under it
sit **Files** (file $\to$ responsibility), an actionable **Build** checklist (each
action is its own checkbox and names its file), a **Tests** checkbox, and the
**Accept / Measure / Gate / Rollback** criteria (§4.1). Steps 0.1–0.5 and 1.1–1.4
are the recommended near-term work and run **regardless** of the probe; 2a and 2b
are mutually exclusive, selected by Step 1.4.

#### Phase 0 — the board + the broad no-regret levers

- [x] **Step 0.1 — S1: honest per-layer gates for every toolchain** $\to$ `src/mu/agent.py` *(no flag — only tightens gate truth; the p7-class fix)* — ✅ **done 2026-06-20** (`_vacuous_log`/`_vacuous_pass` added; 27 unit tests; full suite 234 green; archive-replay Accept runs next dojo cycle)
- **Files.** `src/mu/agent.py` — the gate logic (`_make_vacuous`, `_test_passed`);
  new `tests/test_vacuous_all_toolchains.py` — the regression tests.
- **Build:**
  - [x] In `src/mu/agent.py`, extend the `_make_vacuous` predicate family with one
     sentinel matcher per toolchain: pytest/unittest `collected 0 items` / `no tests
     ran`; `go test` `no test files`; `cargo test` `running 0 tests`; `dotnet test`
     0-total (`Failed: 0, Passed: 0`), `No test is available`, or `Build FAILED` with
     process exit 0; `jest`/`vitest` `No test files found` / `Tests: 0 passed`.
  - [x] In `src/mu/agent.py`, route *every* per-problem and staged test gate through
     `_test_passed` so the vacuous predicate is applied uniformly.
- [x] **Tests.** Per toolchain: (a) a vacuous sentinel log $\Rightarrow$ `_test_passed` False; (b) a
  genuine green log $\Rightarrow$ True (no false-negative); (c) a genuine failing log $\Rightarrow$ False.
- **Accept.** Replay every archived `tests-final.log` across all ten problems:
  **zero** genuine passes reclassified as failures; every "0 tests" / "nothing to be
  done" / "Build FAILED, exit 0" caught.
- **Measure.** Count reclassified archive sessions per problem (expect false-passes
  beyond p7).
- **Gate (proceed).** 0 false-negatives on archived genuine passes across all
  toolchains $\Rightarrow$ the board is honest for the whole set.
- **Rollback.** Sentinels are additive predicates — delete them; the gate reverts.

- [x] **Step 0.2 — the whole-set board + `mu dojo board`** $\to$ `src/mu/dojo/measure.py`, `src/mu/dojo/cli.py` *(depends on 0.1)* — ✅ **done 2026-06-20** (10 unit tests; **Accept met**: on the L0 board the per-layer parse reconstructs the observed solved count exactly, 0.80 = 0.80. Fixed the self-consistency check to compare the *raw* layer-parse vs observed — the smoothed `E[#solved]` is biased high at small n by the Beta-Binomial prior, so it's reported separately, not used for the check.)
- **Files.** `src/mu/dojo/measure.py` — `_layer_clears` + board aggregation;
  `src/mu/dojo/cli.py` — the `mu dojo board` subcommand; new `tests/test_board.py` —
  fixture-log assertions.
- **Build:**
  - [x] In `src/mu/dojo/measure.py`, add `_layer_clears(session_dir)` (§A.4) — each
     problem declares its own layers (a trivial problem has one).
  - [x] In `src/mu/dojo/measure.py`, aggregate the N runs into a `capability.Board` and
     emit, for all ten: per-layer $\hat q$ (+CI), per-problem `p_solve`, the
     `bottleneck`, and `e_solved(board)` (+CI).
  - [x] In `src/mu/dojo/cli.py`, add a `mu dojo board` subcommand that runs the set,
     prints the table, and writes the JSON the loop reads.
- [x] **Tests.** Exact per-layer booleans on committed fixture logs per toolchain; a
  missing/garbled log $\Rightarrow$ "not cleared", never a crash.
- **Accept.** Set-level self-consistency: `e_solved` ($\sum$ `p_solve`) $\approx$ the observed
  count of solved problems within CI, and each `p_solve_i` $\approx$ that problem's measured
  pass-rate.
- **Measure.** This *is* the instrument — it produces the board every later step
  ranks on and diffs against.
- **Gate.** Self-consistency holds $\Rightarrow$ the board is trustworthy as ranking + ledger.
- **Rollback.** Additive subcommand + JSON keys; drop them.

- [x] **Step 0.3 — S2: cross-stage type-ownership reflex** $\to$ `src/mu/reflexes/csharp/` *(catalogued reflex, on-by-default iff it KEEPs)* — ✅ **ablation done → PARKED behind `MU_S2_TYPE_REFLEXES` (default off).** p10 0/15 ON=OFF, Gate 1 FAIL; p4 unharmed. Re-eval (`abl_s2b`) after the MSB1003 fix still 0/15=0/15. Full numbers + the NU1202-wall reframing: **[`docs/ablations.md`](../ablations.md)**. Instrument fixes shipped first (`b27effb`): `noted`/`_fired` honor `MU_DISABLE_REFLEX`; `mu dojo measure` emits per-layer q̂. **Lesson:** the next p10 lever must attack whatever fails the backend build *first*, not cross-stage types.
- **Files.** `src/mu/reflexes/csharp/fix_csharp_cross_stage_duplicate_types.py` and
  `src/mu/reflexes/csharp/fix_csharp_public_signature_accessibility.py` — the two
  reflexes; `src/mu/reflexes/registry.py` — the catalogue slot; `src/mu/agent.py` —
  the reapply wiring; new `tests/test_csharp_cross_stage_types.py`.
- **Build:**
  - [x] Add `src/mu/reflexes/csharp/fix_csharp_cross_stage_duplicate_types.py` —
     ownership prefers the **non-test** file (a `backend.Tests/` dir sorts *before*
     `backend/`, so pure sort order is wrong); strip the cross-stage duplicate type
     blocks $\to$ CS0101); see §A.3.
  - [x] Add the CS0053 sibling
     `src/mu/reflexes/csharp/fix_csharp_public_signature_accessibility.py` (raise an
     `internal` type referenced by a `public` signature to `public`).
  - [x] In `src/mu/reflexes/registry.py`, catalogue both (`duplicate-declaration`
     and a new `type-visibility` slot); the catalogue-completeness test passes.
  - [x] In `src/mu/agent.py`, wire both into the `_inter_stage_gate` (project-wide,
     before the backend gate compiles).
- [x] **Tests.** Dup type across two stage files $\Rightarrow$ exactly one removed (backend kept); a
  legitimately distinct same-named type in a different namespace $\Rightarrow$ **not** removed;
  the CS0053 case $\Rightarrow$ becomes `public`; idempotent (double-apply stable, I5).
- **Accept.** Dry-run replay of archived p10 CS0101/CS0053 sessions $\Rightarrow$ the guard
  resolves them.
- **Measure.** Ablation: `mu dojo measure p10 -n 15 --disable
  fix_csharp_cross_stage_duplicate_types` vs enabled; also run p4. $\beta$ = $\Delta$(backend-layer
  $\hat q$) with CI; record an `efficacy_run` row.
- **Gate (KEEP; pre-registered, I6).** backend-layer $\hat q$ $\Delta$ CI lower bound
  **> 0** AND p4 pass-rate $\Delta$ CI lower bound **$\ge$ −0.05** (I4) $\Rightarrow$ on by default.
  Otherwise keep disabled-by-default behind the ablation flag.
- **Rollback.** Catalogued reflex — the ablation path removes it; default-disable is
  a one-line registry flip.

- [x] **Step 0.4 — S3/S4: one reconciliation routine + detector + level record** $\to$ `src/mu/agent.py`, `src/mu/scaffold.py` *(behaviour-preserving refactor)* — ✅ **done 2026-06-20** (6 unit tests; suite 258 green — legacy path byte-identical, I1 confirmed)
- **Files.** `src/mu/agent.py` — `reconcile_provided` + the `meta.json` writes;
  `src/mu/scaffold.py` — `is_fullstack_dotnet_vue`; new `tests/test_reconcile.py`.
- **Build:**
  - [x] In `src/mu/agent.py`, factor the `agent.py:~678` "mark a provided file done"
     logic into `reconcile_provided(plan_file, p, owned_paths=None)` (the model owns
     the rest and may neither rewrite nor redeclare the owned set).
  - [x] In `src/mu/scaffold.py`, add `is_fullstack_dotnet_vue(signal)`.
  - [x] In `src/mu/agent.py` / `src/mu/archive.py`, write `meta.json.minimize` (and a
     `meta.json.scaffold` slot) on every run (env-driven; `L0` default).
- [x] **Tests.** Provided files marked done; with S2, the model cannot re-add a provided
  type; the detector fires on a synthetic full-stack goal but not on p1; `meta.json`
  carries the level.
- **Accept.** With `owned_paths=∅` the refactor is byte-identical (I1); the full
  suite is unchanged.
- **Gate.** Suite green, no behaviour delta $\Rightarrow$ proceed.
- **Rollback.** Inline the function back; remove the meta keys.

- [x] **Step 0.5 — L0 baseline** $\to$ *no new file — runs the instrument* *(records, does not gate)* — ✅ **recorded 2026-06-20** (`qwen2.5-coder-3b-instruct`, N=5 → `.mu/board_L0_3b.json`). **L0 board: only p1-helloworld solves (4/5); p2–p9 all 0/5; p10 0/5 on all four layers.** layer-parse 0.80 = observed 0.80; smoothed E[#solved] 1.86. ⚠️ ~~**Capacity blocker:** qwen-7b won't load on this 8 GB host~~ **RESOLVED 2026-06-22:** the blocker was the Q4_K_M quant (~4.7 GB); the **Q3_K_L** quant (4.09 GB resident) fits and runs. A full 8 GB model sweep (commit `74f38c8`, `docs/quantization-and-the-stack.md`) picked **qwen2.5-coder-7b-instruct Q3_K_L** as the empirical winner — **7/10** solved; the real L0 reference is now `.mu/board_L0_7b.json` (p10 0/5, bottleneck `backend_build` q̂=0.14), superseding the 3b board. The 0.3 ablation/KEEP gates now have real headroom and are running here.
- [ ] **Build:** Run `mu dojo board` over all ten plus `mu dojo measure p10 -n 15`,
  post S1–S4; record an `efficacy_run` with per-layer $\hat q$. This board is the L0
  reference P1/P2 are measured against for every arm.
- **Backend-build bottleneck diagnosis (2026-06-23).** Archive scan of the 12 most
  recent 7b p10 sessions (the loop's step-2 "candidate from $\arg\min\hat q$" =
  `backend_build`) gives the *first* gate error: **MSB1003 ×8**, CS0101 ×3, CS0246
  ×1 — **refreshing §0.3's stale CS0101-led table**: on the 7b winner the bottleneck
  *within* `backend_build` is **structure (where `dotnet test` runs)**, not
  cross-stage types — the direct reason S2 (0.3) showed no effect. **Root cause:** the
  model authors `## Test Command: dotnet test tests/` (a conventional separate xUnit
  project) but the writer builds a *single* root project and never creates
  `tests/*.csproj`; `normalize_test_command`'s `dotnet test <dir>`→root redirect
  (`plan.py:428`) **only fired when `tests/` already existed** (`arg_path.is_dir()`),
  but it runs at *grounding* time — before the writer creates `tests/` — so it no-oped
  and the stale command reached the gate as MSB1003. **Fix (no-regret normalizer
  timing fix, not a gated lever):** redirect whenever `<dir>` resolves to no `.csproj`
  (absent / a file / csproj-less dir), leaving a real `tests/*.csproj` untouched
  (`plan.py`, 5 tests in `tests/test_dotnet_test_dir_redirect.py`; suite 300 green).
  **A/B DONE 2026-06-23** (qwen-7b, N=15, p10 ON/OFF + p4 control, `.mu/abl_msb_verdict.md`;
  prereg `.mu/abl_msb_prereg.md`, OFF arm = parent `plan.py` swapped by git). **The fix
  works mechanically — MSB1003 eliminated 10/15 → 0/15** (ON-arm first-errors carry
  zero MSB1003; every run now reaches `Determining projects to restore…`, i.e. `dotnet
  test` resolves a project and the build *enters compilation*). But **`backend_build`
  stays 0/15** (Δq̂ −0.001, Gate 1 FAIL; p4 control PASS 13/15 vs 12/15) — the bottleneck
  **moved one layer deeper**, exactly the S2 lesson (Result 2/3). New `backend_build`
  first-errors (ON arm): **CS0246 ×6** (dominant: *"the type `Program` could not be
  found"* — the `WebApplicationFactory` test can't see the minimal-API `Program`) +
  **CS0101 ×6** (duplicate types) + CS1026/CS1513 ×2. **Fix RETAINED (no-regret).**
  **Decisive corollary:** S2's null ablation was a *masking* artifact — MSB1003 fired
  before CS0101 ever arose; now CS0101 is reachable (6/15), so **S2 warrants
  re-evaluation**, and a new **CS0246 `Program`-visibility** fix (add `public partial
  class Program {}` to the API for `WebApplicationFactory` — S5 test-authoring) is the
  other half of the now-exposed coordination layer. These two are the aimed candidates
  for the next loop pass / Phase 1 probe.

- [x] **Step 0.6 — S6: bottom-up dependency build order** $\to$ `src/mu/plan.py`, `src/mu/incremental.py`, `src/mu/agent.py` *(general no-regret lever; flag `MU_BUILD_ORDER`)* — 🟡 **slices 1–4 done 2026-06-22** (commits `54ffb3f`, `a198241`): ordering + incremental Makefile + per-slice gate dedup; **26 unit tests** (`test_build_order` 15 + `test_incremental` 11), suite 291 green; off ⇒ byte-identical (I1).
- **Files.** `src/mu/plan.py` — `build_rank`/`build_order`/`reorder_plan`; `src/mu/incremental.py` — `BuildLedger`, Makefile weaving (`add_target`/`append_check`), `unit_check_command`, `gate_key`/`verifiable_now`; `src/mu/agent.py` — gated wiring; `tests/test_build_order.py`, `tests/test_incremental.py`.
- **Build:**
  - [x] **Ordering** — `plan.build_rank` (0 manifests/Makefile · 1 headers+type/model/schema decls · 2 core · 3 wiring/entry · 4 tests; camelCase/separator tokenisation + dir-role hints, plural-tolerant), `build_order`, `reorder_plan` (rewrite `## Files`, preserves status+desc+non-task lines, idempotent), wired after grounding/reconcile.
  - [x] **Incremental Makefile** — `incremental.append_check` weaves each source slice's cheap unit check (`py_compile`/`cc -fsyntax-only`) into a growing `make check` target as it passes lint; idempotent + ledger-tracked, so never a trailing/up-front blob and never woven twice.
  - [x] **Per-slice gate + no-double-build** — `BuildLedger` records each (command, mtime-keyed build-state) gate; the per-iteration test gate and the final gate share it, so an already-green state is not tested twice (the "each slice knows what's built earlier" requirement). Forward-dep-safe via `verifiable_now`.
  - [ ] **`run_staged` (p10) wiring** — follow-up; this slice covers the single-`run` path.
- **Measure / Gate.** A/B `mu dojo measure` with `MU_BUILD_ORDER` on vs off, KEEP iff $\Delta E[N_{\text{solved}}]$ CI lo **> 0** (P1) ∧ no control regression (P2). **Run 1 done 2026-06-22** (qwen-7b, p1/p2/p3 × on/off × N=15, `.mu/abl_bo_verdict.md`): **caught a REGRESSION** — p3-sdl2 cratered **15/15→2/15** ON (ΔE[#solved] −0.71, CI [−1.04, −0.34], P1/P2 FAIL). p1 control clean (15/15 both), p2 neutral (14 vs 13). **Root cause + fix (commit `008d4ce`):** `incremental.append_check` prepended `.PHONY: check` to the Makefile TOP → a makefile reflex re-ran and tab-indented the `CFLAGS`/`LDFLAGS` assignments → `$(CFLAGS)` empty → `cc -o main main.c` with no sdl2 flags. Now `.PHONY`/target append at the END; regression test added. **Re-measure confirms the fix: p3-sdl2 ON 15/15 = OFF 15/15.** Refreshed verdict: **ΔE[#solved] +0.06, CI [−0.26, +0.38] — P2 PASS (no regression), P1 FAIL (no significant lift) → S6 stays OPT-IN** (`MU_BUILD_ORDER` off by default). Exactly the prereg expectation: build-order is pass-rate-neutral on easy problems (they pass on 7b anyway), and a mild repair-iters *cost* here (+0.4 p2, +0.9 p3) — its real payoff is cascade-control on hard multi-layer goals (p10), un-demonstrable until p10's backend builds. **No-regret: shipped, tested, available behind the flag, not auto-applied.**
- **Rollback.** `MU_BUILD_ORDER` off restores baseline (already the default).

#### Phase 1 — Approach B as the $\delta$-probe (instrumental; never shipped, I7)

- [ ] **Step 1.1 — author the fixture rung-deltas** $\to$ `dojo/fixtures/p10/`
- **Files.** `dojo/fixtures/p10/L2/…`, `dojo/fixtures/p10/L3/…`,
  `dojo/fixtures/p10/L4/…` (committed via the `.gitignore` golden-file exception
  fixtures already use).
- [ ] **Build:** Hand-author `dojo/fixtures/p10/{L2,L3,L4}/` as *correct*, offline,
  dependency-free boilerplate, each rung the delta over the one below (§A.2 layout).
- **Accept.** Built once by hand: each rung, applied over the rungs below it, yields
  a tree that builds/tests by construction.
- **Rollback.** Delete the directory; `minimize` returns to L0.

- [ ] **Step 1.2 — level-aware `fixtures.apply`** $\to$ `src/mu/fixtures.py`, `src/mu/dojo/runner.py`
- **Files.** `src/mu/fixtures.py` — the level-aware `apply`; `src/mu/dojo/runner.py` —
  the apply hook; new `tests/test_fixtures_levels.py`.
- **Build:**
  - [ ] In `src/mu/fixtures.py`, make `apply` rung-aware (§A.2): apply every rung up to
     the problem's `minimize` level; rung-prefixed files apply only when their rung
     $\le$ target, unprefixed files always apply (keeps flat fixtures like p6-rust
     working).
  - [ ] In `src/mu/dojo/runner.py`, call `fixtures.apply` before the agent subprocess.
- [ ] **Tests.** Right subset per rung; idempotent; flat/unset level $\Rightarrow$ today's
  behaviour (I1); off $\Rightarrow$ no-op.
- **Accept.** Applying L3 lays exactly L2$\cup$L3; an L4 run lays L2$\cup$L3$\cup$L4.
- **Rollback.** Single-rung copy is the existing path; revert the function.

- [ ] **Step 1.3 — measure the staircase** $\to$ `problems-catalog.json` (set `minimize`); no new code
- [ ] **Build / measure:** Set p10's `minimize` field (in `problems-catalog.json`)
  to L2, then L3, then L4 across runs; `mu dojo measure p10 -n 15` at each; record
  per-layer $\hat q$ and mean $k/4$ with bootstrap CI at each rung, plus the L0 board
  from 0.5. Every figure carries its rung (I3).

- [ ] **Step 1.4 — identify $\delta$ and read the decision gate** $\to$ *no new file — analysis*

**Compute.** $\hat\delta_\ell \approx \operatorname{logit}\hat q_\ell|_{\text{rung that pins }\ell} - \operatorname{logit}\hat q_\ell|_{\text{rung below}}$;
bottleneck $= \arg\min_\ell \hat q_\ell$ at L0/L2. **Decision gate (pre-registered, I6):**

| Observation | Inference | Next |
|---|---|---|
| jump at **L2**, bottleneck a *build* layer | structure binds | Step 2a (A) |
| jump only at **L3**, bottleneck a *test* layer | coordination + test-authoring binds | Step 2b (C + S5) |
| no jump until **L4** | irreducible model-logic ceiling | **kill A/C**; `route()` p10 (`MU_ROUTE`); keep the L3 fixture as a labelled regression signal only |

The L4 row is an explicit **kill criterion** — be willing to conclude "no
minimization lever ships" and stop.

#### Phase 2 — build exactly one lever (selected by 1.4), then calibrate

- [ ] **Step 2a — Approach A: stage-aware self-scaffold** $\to$ `src/mu/scaffold.py`, `src/mu/agent.py` *(only if 1.4 said "structure"; flag `MU_SCAFFOLD`)*
- **Files.** `src/mu/scaffold.py` — stage-aware `detect` + generator invocation;
  `src/mu/agent.py` — the per-stage hook in `run_staged`; `dojo/scaffolds/vite-vitest/` —
  vendored offline fallback; new `tests/test_scaffold_stage.py`.
- **Build:**
  - [ ] In `src/mu/scaffold.py`, make detection stage-aware: `detect(Signal, stage)`
     (§A.1).
  - [ ] In `src/mu/agent.py`, at the top of each `run_staged` session **before**
     `ground_plan`, have mu invoke the toolchain's own generator (`dotnet new
     webapi`+EF on backend, `dotnet new xunit` on integration, `npm create vite` on
     frontend) — mu's own output (I7) — and record `meta.json.scaffold`.
  - [ ] In `src/mu/scaffold.py`, copy the vendored `dojo/scaffolds/vite-vitest/` only
     when offline (I2; prefer the tool-invoked path, §0.2 tension).
- [ ] **Tests.** Stage-aware detection (frontend stage $\Rightarrow$ vite, not webapi); offline
  guarantee (network blocked $\Rightarrow$ vendored or baseline, no crash); scaffold-then-ground
  reconciliation (no `dotnet new` exit-73 collision); off $\Rightarrow$ no-op (I1).
- **Measure / Gate.** A/B vs the 0.5 L0 baseline + controls; **KEEP iff P1$\wedge$P2**
  (§4.2) and §2.3 (p10 pass-rate CI lo > 0 or $k/4$ $\uparrow$ with CI$\not\ni$0).
- **Rollback.** `MU_SCAFFOLD` off restores baseline.

- [ ] **Step 2b — Approach C: contract + S5 test skills** $\to$ `src/mu/agent.py` (+ `src/mu/reflexes/`) *(only if 1.4 said "coordination + test"; contract flagged)*
- **Files.** `src/mu/agent.py` — the contract injection in `_run_architect_pass`
  (reuses the S2 guard from 0.3, no new reflex needed for the backstop); **S5**
  test-authoring skills as new reflexes under `src/mu/reflexes/csharp/`
  (WebApplicationFactory) and `src/mu/reflexes/javascript/` (Vitest fetch-mock), or
  as writer/architect prompt additions in `src/mu/agent.py`; new
  `tests/test_contract.py`.
- **Build:**
  - [ ] In `src/mu/agent.py`, inject the full-stack contract in `_run_architect_pass`
     for the detected stack (manifest + route + JSON shape + test cmd + single-owner
     type table; §A.3), capability-keyed. It **reuses S2** (shipped in 0.3) as the
     deterministic backstop — contract advisory, guard enforcing.
  - [ ] Add **S5** test-authoring skills (a `WebApplicationFactory` integration-test
     skill in `src/mu/reflexes/csharp/`, a Vitest fetch-mock skill in
     `src/mu/reflexes/javascript/`) iff 1.4 localized the ceiling to test logic.
- [ ] **Tests.** Contract injected only for full-stack goals; the S2 backstop fires when
  the model violates the type ledger; the skills load for the right stack.
- **Measure / Gate.** A/B vs baseline + controls (esp. **p4**); **KEEP iff P1$\wedge$P2**.
- **Rollback.** Contract flag off; S2 stays (it's no-regret).

- [ ] **Step 2c — calibrate the model** $\to$ `src/mu/dojo/measure.py` (reads `src/mu/capability.py`) *(do before declaring 2a/2b shipped)*
- [ ] **Check.** In `src/mu/dojo/measure.py` (querying `src/mu/capability.py`), compare
  the model's **predicted** `expected_solve_gain` (pre-ship fit) with the
  **measured** $\Delta$`p_solve`. If $|\text{predicted}-\text{measured}|$ exceeds the
  measurement CI, the model is miscalibrated $\to$ do **not** trust its rankings:
  widen N, refit (§1.4), re-derive the next step. Keeps §1 a falsifiable predictor.

#### Phase 3 — record & generalize $\to$ docs + `TODO.md`
- [ ] Update `docs/problems/p10-dotnet-vue-blog.md`,
  `docs/challenges/csharp-aspnet-scaffolding.md`, `TODO.md`, and this plan's results
  table; **every figure carries its L-level** (I3).
- [ ] Promote any *general* capability that earned KEEP (S2; a contract/self-scaffold
  `reduce()` step) toward the product path per memory `agent-self-minimization`.

### 4.4 Risk register

| Risk | Phase | Detector | Mitigation |
|---|---|---|---|
| Honest gate flags a *genuine* pass | 0.1 | archive replay reclassifies a real pass | scope to exact sentinels; regression test on genuine passes |
| Log-parse drift corrupts $k/4$ | 0.2 | self-consistency breaks | parse stable substrings; unknown $\Rightarrow$ "not cleared" |
| S2 deletes a legitimately distinct same-named type | 0.3 | the "distinct type kept" test fails; p4 regresses | exact-block match, namespace-aware; ablation + control gate |
| Cross-level comparison inflates a result | all | a number lacks an L-level | I3 test: `meta.json.minimize` required |
| A's scaffold needs the network mid-run | 2a | offline test fails | tool-invoked first; vendored fallback (I2); online opt-in |
| Model ignores C's contract | 2b | CS0101 reappears | S2 backstop enforces deterministically |
| Capability model mis-ranks | 2c | predicted vs measured $\Delta$ diverge | calibration gate (2c) |
| p10 is pure model-ceiling; effort wasted | 1 | no jump until L4 | the L4 **kill criterion** stops A/C; route instead |

### 4.5 Statistical power & cost

The loop proves **P1** on $E[N_{\text{solved}}]$ — a *sum* over ten, whose CI is
tighter than any single problem's — so a broad lever adding ~0.1–0.3 is detectable
at **N$\approx$10–15 per problem**, whereas a binary pass-rate shift 0$\to$0.2 needs $\approx$N=50; the
continuous per-layer $\hat q$ detects the shift even earlier (Result 3). Every gate
keys on $\hat q$/$E[N_{\text{solved}}]$ first, confirms with pass-rate. Budget: a
problem $\approx$ 60–300 s/run on the 8 GB M2 $\Rightarrow$ a full **board** (ten $\times$ 15) $\approx$ half a day; a
per-step ablation re-runs only the **covered** problems plus controls. Reuse
`efficacy_run`/Beta-Binomial rather than re-rolling stats.

---

## 5. Appendix A — worked code against the current tree

Illustrative, not final — each snippet names the real symbol it extends. Verified
against the tree at 2026-06-19 (capability.py: 2026-06-20).

### A.1 Approach A — `scaffold.py` per stage (mu invokes the generator itself)

Today `scaffold.detect(sig)` returns the first matching recipe globally, and
nothing calls it. The fix: (1) make detection stage-aware, (2) call it at the top
of each staged session in `run_staged` ([agent.py](../../src/mu/agent.py):2109).
Off-path stays byte-identical (`scaffold.enabled()` is `MU_SCAFFOLD=="1"`).

```python
# src/mu/scaffold.py — detection depends on the stage the architect is on.
_STAGE_PRIORITY: dict[str, tuple[str, ...]] = {
    'backend':  ('dotnet-webapi', 'dotnet-xunit', 'cargo-bin'),
    'frontend': ('vite-vitest',),
    'model':    ('dotnet-webapi', 'cargo-bin'),
}

def detect(sig: Signal, stage: str | None = None) -> Optional[Recipe]:
    """First recipe whose predicate matches. With *stage* given, only recipes
    relevant to that stage are eligible (so the frontend stage can't be captured
    by the backend's dotnet-webapi — the bug that sank the first wiring)."""
    eligible = RECIPES
    if stage and stage in _STAGE_PRIORITY:
        names = _STAGE_PRIORITY[stage]
        eligible = tuple(sorted((r for r in RECIPES if r.name in names),
                                key=lambda r: names.index(r.name)))
    return next((r for r in eligible if r.detect(sig)), None)
```

Each recipe runs the **toolchain's own generator** (`dotnet new webapi`,
`npm create vite`) — mu's own output, satisfying §0.2. The vendored copy under
`dojo/scaffolds/vite-vitest/` is copied only when `online_enabled()` is false (the
air-gapped fallback, and the one part in tension with the principle — prefer the
tool-invoked path). Call `scaffold.detect(sig, stage=stage_name)` at the top of
`run_staged`'s loop, **before** `run()` executes the stage, so the existing
fixture-detection at `agent.py:678` marks scaffold-owned files done.

### A.2 Approach B — level-aware `fixtures.apply` (probe only)

`fixtures.apply` ([fixtures.py](../../src/mu/fixtures.py)) currently copies *all*
of `dojo/fixtures/<id>/`. To climb the ladder, lay fixtures out as per-rung deltas
and apply every rung **up to** the problem's `minimize` level:

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

def apply(problem_id: str, work_dir: str = '.', level: str | None = None) -> list[str]:
    """Copy a problem's committed fixtures into *work_dir*, up to *level* (the
    problem's `minimize` rung by default). A rung-prefixed file (L2/…) applies only
    when its rung ≤ target; an unprefixed file always applies (flat fixtures)."""
    src = fixture_dir(problem_id)
    if not src.is_dir():
        return []
    target = level or _minimize_level(problem_id)
    rungs = _LADDER[:_LADDER.index(target) + 1] if target in _LADDER else _LADDER
    provided: list[str] = []
    for f in sorted(p for p in src.rglob('*') if p.is_file()):
        rel = f.relative_to(src)
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

The agent already marks any pre-existing planned file done (`agent.py:678`), so no
agent change is needed. **Honesty (I3, I7):** every reported pass carries its rung;
an L3 pass is never compared to L0, and these fixtures never ship on the product
path — they exist solely to identify $\delta$.

### A.3 Approach C — contract + cross-stage type-ownership reflex (S2)

A deterministic L1 contract injected by the architect (`_run_architect_pass`,
[agent.py](../../src/mu/agent.py):2009) for the detected full-stack stack:

```python
# src/mu/agent.py — after arch_text is written, for a multilayer dotnet+node goal.
if _is_multilayer(goal) and {'dotnet', 'node'} <= _goal_toolchains(goal):
    contract = (
        "\n## Type Ownership (one definition site each — do not redefine)\n"
        "- `Post` (Id:int, Title:string, Content:string) — backend/Models/Post.cs, public\n"
        "- `BlogContext : DbContext` — backend/Data/BlogContext.cs, public\n"
        "- the test project REFERENCES these via ProjectReference; never redeclares\n"
        "\n## Contract\n"
        "- route: GET /api/posts -> 200 JSON array of Post; seed one Title='Hello World'\n"
        "- test cmd: dotnet test backend.Tests && (cd frontend && npx vitest run)\n"
    )
    Path('ARCHITECTURE.md').write_text(arch_text + contract)
```

The contract is advisory; what actually kills CS0101/CS0053 is the deterministic
guard (one-file-per-reflex, [registry.py](../../src/mu/reflexes/registry.py)):

```python
# src/mu/reflexes/csharp/fix_csharp_cross_stage_duplicate_types.py
import re
from pathlib import Path

_DECL = re.compile(r'(?m)^\s*(?:public\s+|internal\s+)?(?:sealed\s+)?'
                   r'(?:class|record|struct)\s+(\w+)')

def fix_csharp_cross_stage_duplicate_types(project_dir: str) -> bool:
    """Keep one definition of each type — the one under the backend source dir —
    and delete the duplicates the staged writer re-declared elsewhere (CS0101).
    General to any multi-project .NET layout; never touches a uniquely-named type."""
    cs = [p for p in Path(project_dir).rglob('*.cs')
          if not any(s in p.parts for s in ('obj', 'bin'))]
    owners: dict[str, Path] = {}
    # Non-test files first (a `backend.Tests/` dir sorts BEFORE `backend/` because
    # '.' < '/', so pure sort order would make the test the owner — wrong).
    for f in sorted(cs, key=lambda p: (any('test' in s.lower() for s in p.parts), str(p))):
        for name in _DECL.findall(f.read_text(errors='ignore')):
            owners.setdefault(name, f)         # first non-test site = owner
    changed = False
    for f in cs:
        text = f.read_text(errors='ignore')
        for name in set(_DECL.findall(text)):
            if owners.get(name) != f:
                text = _strip_type_block(text, name)
                changed = True
        if changed:
            f.write_text(text)
    return changed
```

Wire into `apply_csharp_repair_reflexes` and the `_inter_stage_gate` reapply path;
catalog under `'duplicate-declaration'`; add idempotency + "leaves a uniquely-named
type alone" tests. CS0053 gets a sibling that raises a type behind a `public`
signature to `public`.

### A.4 Per-layer $\hat q$ in `measure.py`

The metric is a direct read-out of §1. Sample each run's per-layer clears from the
staged gate logs, then aggregate; honest only if S1 rejects vacuous passes.

```python
# src/mu/dojo/measure.py
_P10_LAYERS = ('backend_build', 'backend_test', 'frontend_build', 'frontend_test')

def _layer_clears(session_dir: Path) -> dict[str, bool]:
    """One run's per-layer pass/fail — the model's q_{i,ℓ} samples."""
    text = '\n'.join(p.read_text(errors='ignore')
                     for p in (session_dir / 'logs').glob('*.log'))
    return {
        'backend_build':  'Build succeeded' in text and 'error CS' not in text,
        'backend_test':   bool(re.search(r'Passed!\s+-\s+Failed:\s+0', text)),
        'frontend_build': 'vite build' in text and 'error TS' not in text,
        'frontend_test':  bool(re.search(r'Test Files\s+\d+ passed', text)),
    }
```

Collect `_layer_clears` across the N runs (sessions via `sessions.latest_since`),
build a `capability.Layers`/`Board`, and emit `p_solve`/`bottleneck`/`k_mean`
(= $\sum\hat q$) in the `--emit-json` block next to `pass_rate`.

### A.5 `capability.py` — the fitted model as one shared component (shipped)

Already in tree as [`src/mu/capability.py`](../../src/mu/capability.py): a thin,
pure layer over `observe.py` (Beta-Binomial $\hat q$) and `reflexdb.py` (efficacy
$\beta$) that A, B, C, routing, and `practice` all call.

```python
@dataclass(frozen=True)
class LayerStat:                 # clears out of n attempts for one layer
    clears: int; n: int
    @property
    def q(self) -> float:        # smoothed q̂ (Beta-Binomial posterior mean)
        return observe.beta_binomial(self.clears, self.n).rate

Layers = dict[str, LayerStat]    # layer -> stat
Board  = dict[str, Layers]       # problem id -> its layers

def p_solve(layers):             # ∏ q̂  — chain / series system (the model's P_i)
def bottleneck(layers):          # argmin q̂  — the layer the next step targets
def expected_solve_gain(layers, layer, dq):   # dq · ∏ siblings — Result 2 marginal
def route(layers, eps=0.02):     # p_solve < eps  → skip this (model, problem)
def e_solved(board):             # Σ_i p_solve_i  — the objective the loop raises
def portfolio_gain(board, targets, beta):     # Σ expected_solve_gain over covered (i,ℓ)
def rank_portfolio(board, candidates):        # rank by ΔE[N_solved] per unit cost
```

`portfolio_gain` sums across **all** covered problems, so a broad reflex (helps p4
*and* p10) outranks a p10-only lever (§0.1). The provable-improvement gate (§4.2)
reads off the board: ship iff re-measured `e_solved` rose with a CI excluding 0
(**P1**) and no problem's pass rate regressed (**P2**). Consumers: `measure.py`
builds the `Board` from `_layer_clears` over all ten; the loop ranks with
`rank_portfolio` and tracks `e_solved` as the monotone ledger; **A** reads
`bottleneck`/`expected_solve_gain` to scaffold only where it pays; **C** registers
its reflex with its coverage; **B** supplies the $\delta$-jumps that calibrate the
`LayerStat`s; `practice` and `dojo run --route` call `route`. One object, every
consumer.

---

## 6. Out of scope: constrained decoding

Grammar-/type-constrained decoding (mask tokens that break syntax or static types)
would make structure deterministic at generation time — the most powerful
determinism lever in the literature, and one that needs no pregenerated code. It is
**not feasible in mu today**: mu drives models through LM Studio's
OpenAI-compatible *chat* endpoint, which exposes no per-token logit mask. Pursuing
it would mean a different inference path (e.g. llama.cpp grammars) — a larger
architectural change than this report's scope, recorded as the long-horizon option
if mu ever takes token-level control of generation.

## 7. References

- [Thoughtworks — *Spec-driven development* (2025)][tw]
- [GitHub — *Spec-driven development with AI (spec-kit)*][ghspec]
- [*Spec-Driven Development: From Code to Contract in the Age of AI Coding Assistants* — arXiv:2602.00180][sdd]
- [*Skeleton-Guided-Translation: A Benchmarking Framework for Code Repository Translation* — arXiv:2501.16050][skel]
- [*A Test-Driven-Development Benchmark for LLM Code Generation* — arXiv:2505.09027][tdd]
- [*Constraint decay: The Fragility of LLM Agents in Backend Code Generation* — arXiv:2605.06445][decay]
- [*Where LLM Agents Fail and How They Can Learn From Failures* — arXiv:2509.25370][fail]
- [*Hallucination Cascade: Error Propagation in Multi-Agent LLM Systems* — arXiv:2606.07937][casc]
- Constrained/grammar decoding (§6): [*Correctness-Guaranteed Code Generation via Constrained Decoding* — arXiv:2508.15866](https://arxiv.org/abs/2508.15866); [*Grammar-Constrained Decoding for Structured NLP Tasks* — arXiv:2305.13971](https://arxiv.org/abs/2305.13971)

<!-- link reference definitions (render invisibly; resolve the [..][tw] citations above and in the prose) -->
[tw]: https://www.thoughtworks.com/en-us/insights/blog/agile-engineering-practices/spec-driven-development-unpacking-2025-new-engineering-practices
[ghspec]: https://github.blog/ai-and-ml/generative-ai/spec-driven-development-with-ai-get-started-with-a-new-open-source-toolkit/
[sdd]: https://arxiv.org/abs/2602.00180
[skel]: https://arxiv.org/pdf/2501.16050
[tdd]: https://arxiv.org/pdf/2505.09027
[decay]: https://arxiv.org/html/2605.06445
[fail]: https://arxiv.org/abs/2509.25370
[casc]: https://arxiv.org/html/2606.07937
