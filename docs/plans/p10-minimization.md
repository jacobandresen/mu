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

---

## 2. How to compare the three (the measurement is the hard part)

Binary p10 pass-rate is **0** and therefore uninformative — it cannot rank three
interventions that all start from 0. The comparison must use **graded, continuous
signal**, exactly as the efficacy machinery already does for reflex ablations
(`observe.Posterior` Beta-Binomial, `sz5_gate`, `efficacy_run`; AGENTS.md §5z).

### 2.1 The headline instrument: layer-resolution score (k/4)

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

**Do Approach B first — the fixture staircase — as a diagnostic, and let its
result decide whether to invest in A or C.** Concretely:

1. Build the **k/4 layer-resolution metric** (§2.1) and author `dojo/fixtures/p10`
   with the level-aware `apply`.
2. Measure p10 at **L0, L2, L3, L4** (15 runs each). Read the rung where mean k/4
   (and pass-rate) jumps off the floor.
3. Branch on the result:
   - **Jumps at L2** (structure removed ⇒ passes) → the ceiling *was* structure;
     ship **A** (stage-aware scaffold) as the general version, A/B to confirm.
   - **Jumps only at L3** (needs the tests given) → the ceiling is **coordination
     + test-authoring**, not structure → invest in **C** (contract + type ledger)
     and a test-shape skill; A is confirmed not worth shipping.
   - **Only at L4** (needs stubs) → the residue is irreducible model logic ceiling
     → don't build A or C; record p10 as model-ceiling at L0–L3 and route it
     (`MU_ROUTE`) for weak models, climbing the ladder only to keep a deterministic
     regression signal.

This converts an unfalsifiable 0/12 into a **localized, ranked diagnosis** and
turns the "build A or C?" question from a guess into a data-driven choice.

---

## 4. Why this is optimal (the argument)

Treat the decision as one under uncertainty. The binding unknown is **which layer
is p10's true constraint** — structure, coordination, or irreducible logic. We
already paid once for guessing: the dropped scaffolder assumed *structure* and
returned 0→0 with higher cost. Compute expected value, EV ≈ P(moves p10)·value −
cost:

- **A and C** each have **low, unknown** P(success) *given the prior* (structure
  shown not to bind; coordination only *plausibly* binds) and **high** build cost.
  Building either blind repeats the scaffolder mistake — negative-EV in
  expectation until the constraint is known.
- **B** has **P(moves p10) ≈ 1** (pin enough and it passes *by construction*) at
  **low** cost (shipped mechanism), **and** it is the *only* action that resolves
  the binding unknown — it makes P(success) for A and C *computable* instead of
  guessed.

So B strictly dominates as the first move on two independent grounds: it has the
highest immediate, near-certain value, **and** it is a prerequisite that
de-risks the expensive options. In information terms, B maximizes information
gain per unit cost about the one variable that determines whether A or C can ever
pay off. After B, the *targeted* follow-up (A xor C) is chosen against evidence,
so its EV is then positive by construction. The alternative orderings
(A-first or C-first) are dominated: they spend the most to learn the least and
have already failed once. This is the same honest-harness discipline the codebase
mandates ([AGENTS.md](../../AGENTS.md) §0, memory `project-false-pass-gate`,
`feedback-honest-dojo`): don't build a general mechanism until the data names the
class it must target.

A secondary optimality: B is the only option whose *artifacts compose with* the
others — its fixtures double as the offline vendored skeletons Approach A needs
(`dojo/scaffolds/`) and as the golden reference Approach C's type-ledger guard is
validated against. So even when B leads to A or C, nothing built is wasted.

---

## 5. Implementation plan (phased, gated)

**Phase 0 — instrument (no agent change).**
- [ ] Add the **k/4 layer-resolution** scorer to `src/mu/dojo/measure.py` (parse
      the four checkpoints from stage logs; emit `k4_mean` alongside pass rate).
- [ ] Baseline: `mu dojo measure p10 -n 15` at L0; record `efficacy_run`.

**Phase 1 — Approach B (the staircase).**
- [ ] Author `dojo/fixtures/p10/{L2,L3,L4}` correct boilerplate (offline, no deps).
- [ ] Level-aware `fixtures.apply` (read `minimize`; apply rungs ≤ target);
      unit tests: each rung copies the right subset; idempotent; off ⇒ no-op.
- [ ] Measure L2/L3/L4 (15 each). Beta-Binomial Δ + k/4 + stochasticity.
- [ ] **Decision gate (§3.3):** locate the jump rung → pick A, C, or route-only.

**Phase 2a — if "jump at L2" → Approach A.**
- [ ] `detect(Signal, stage)`; `vite-vitest` recipe + vendored `dojo/scaffolds/`.
- [ ] Per-stage scaffold hook before `ground_plan`; `meta.json.scaffold`.
- [ ] A/B vs baseline + controls; ship-on only if §2.3 KEEP criteria met.

**Phase 2b — if "jump at L3" → Approach C.**
- [ ] Full-stack contract template in the architect (manifest + route + JSON +
      test cmd + type-ownership table); capability-keyed; flagged.
- [ ] Deterministic cross-stage guard: dedup CS0101 types (keep backend owner),
      promote CS0053 types to `public`; regression tests incl. a control that a
      legitimately distinct same-named type is **not** deleted.
- [ ] A/B vs baseline + controls (esp. p4); ship-on per KEEP criteria.

**Phase 3 — record.** Update `docs/problems/p10-dotnet-vue-blog.md`,
`docs/challenges/csharp-aspnet-scaffolding.md`, `TODO.md`, this plan's results
table; note the L-level of every reported pass.

**Honesty safeguards throughout.** Capability-only detection for A/C (a synthetic
non-dojo full-stack goal must trigger the same path); fixtures labelled by rung
and never compared across levels; controls p1/p2/p5/p6 must not regress; all
agent-affecting flags default **off** so a live collection run is byte-identical
until a change earns its flip.

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

### A.4 The k/4 layer-resolution metric (shared comparison instrument)

Add to `src/mu/dojo/measure.py` ([measure.py](../../src/mu/dojo/measure.py)),
parsed from the staged session's gate logs — a continuous score that moves while
binary pass is pinned at 0:

```python
def _k4(session_dir: Path) -> int:
    """How many of p10's four verifiable checkpoints a run reached (0–4)."""
    logs = (session_dir / 'logs')
    text = '\n'.join(p.read_text(errors='ignore') for p in logs.glob('*.log'))
    return sum((
        'Build succeeded' in text and 'error CS' not in text,    # 1 backend builds
        bool(re.search(r'Passed!\s+-\s+Failed:\s+0', text)),      # 2 dotnet test green
        'vite build' in text and 'error TS' not in text,          # 3 frontend builds
        bool(re.search(r'Test Files\s+\d+ passed', text)),        # 4 vitest green
    ))
```

`measure.run` already finds the session per run (`sessions.latest_since`); average
`_k4` across the N runs and emit it next to `pass_rate` in the `--emit-json`
block. This is the headline number for every arm in §2.

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
