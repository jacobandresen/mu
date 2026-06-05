# Minimizing the Problem Space & De-randomizing the Formulation

A report on where the dojo's stochasticity comes from and how to cut it — by
shrinking the space of decisions the weak model must make, and by reformulating
each task so fewer of those decisions are coin flips. Grounded in the full model-
tagged data (granite-4.1-3b **n=34, pass 0.33**; qwen2.5-coder-7b **n=32, pass
0.65**).

**What the two-model data adds (and why this matters now):** with a mature
reflex layer, the probabilistic iteration found *no deterministic cause that
recurs across multiple problems* — both models' failures are dominated by
writer-stalls/degeneration ("no distilled cause": 13 granite, 10 qwen) and the
fixable causes are scattered n=1. The next gains are **not** more reflexes; they
are shrinking what we ask the model to decide. Three data facts drive the plan:
1. **Both models write bad Makefiles** — `build-rule-structure` is the top
   firing class for both (granite 1.44, qwen 1.19 firings/session). Providing the
   Makefile as a fixture deletes that entire class.
2. **Competence is sharply per-toolchain.** granite is **0.0 on python/rust/go**;
   qwen is **0.167 on node** (its weakest). Minimization must be *model-aware*:
   scaffold heavily where a model is weak, skip where it is ~0.
3. **The residue is the model ceiling** (degeneration), which no formulation
   change reaches — so over-pinning past that point measures nothing.

---

## 1. Where the variance actually comes from (ranked by evidence)

Every independent decision the model makes under sampling is a stochastic
variable. Ranked by how much they move outcomes in the data:

1. **The planner — the dominant source.** A fresh plan each run (decomposition,
   file names, test command) changes everything downstream. Demonstrated
   directly: `mu dojo measure` runs a problem from a *frozen* plan and gets
   byte-identical results (5/5 with `MU_SEED`), whereas the same problem live
   swings pass↔stall round to round. The plan is the biggest lever.
2. **Inferred structure (the model guessing the contract).** When the goal
   doesn't state the interface, the model invents filenames and exported
   symbols, each a gamble. Evidence: p7-flask's recurring `undefined name 'app'`
   (the test guessed at a structure the impl didn't provide); the
   `from main import app` resolver exists *only because* filenames are unpinned.
3. **Degenerate generation (model-ceiling).** Weak models loop or stall. In the
   granite data this dominates: **~13 of 21 failures distill to "no cause"** —
   the writer produced nothing analysable. This is variance you cannot reflex
   away; it is the model itself.
4. **Manifest / build boilerplate.** The model fabricates `go.mod`, `Cargo.toml`
   deps, npm builtins, and Makefile rules. Granite's failure fingerprint is
   **dominated by `build-rule-structure` (fires 1.44×/session)** — almost all of
   its non-degenerate effort goes into getting Makefiles wrong.
5. **Cross-file coupling.** Multi-file tasks add an import/symbol-resolution
   failure class (test↔impl, p7/p8) and, at the extreme, the p10 multi-project
   ceiling.
6. **Out-of-competence routing.** Granite is **0.0 on python/rust/go** (n=34).
   Running it there is pure noise — guaranteed near-total failure that tells you
   nothing.

The throughline: **most variance is *self-inflicted by the formulation*, not
intrinsic to coding.** The planner, the unstated contract, the fabricated
manifest, and the multi-file coupling are all decisions we *handed* to a
stochastic weak model. Take the decision back and the variance disappears.

---

## 2. Minimizing the problem space — constrain the degrees of freedom

Each lever removes a class of independent decision, shrinking the space the
model samples over.

| Lever | DOF removed | Evidence it helps |
|---|---|---|
| **Pin the plan** (golden/canonical plan; model writes code, not structure) | planner | frozen-plan runs are reproducible (`mu dojo measure`) |
| **Provide the manifest/config/Makefile as a fixture** | build boilerplate | granite's `build-rule-structure` 1.44×/session vanishes if the Makefile is given; go.mod/Cargo.toml/package.json error classes disappear |
| **Pin exact filenames + the test command** | naming | kills the import-mismatch class the `from main import app` resolver patches |
| **Collapse to one file / a fixed layout** | cross-file coupling | removes test↔impl symbol-resolution failures (p7/p8) |
| **State the interface contract in the goal** | structure guessing | `improve-plan` spec reflexes already do a slice of this |
| **Route by competence** (`model_profile.competence_by_toolchain`) | out-of-competence noise | don't run granite on python/rust/go (0.0) — it only adds noise |

Combined, these turn a problem from "make N independent stochastic bets" into
"make 1–2," which is the difference between a 30%-pass coin-flip and a
near-deterministic fill-in.

---

## 3. Shifting the formulation — turn inferred decisions into givens

Minimizing DOF is *how*; reformulating the task is *what you hand the model*.
Each reformulation converts a guessed variable into a fixed one.

1. **From "build an app" → "fill in the blanks."** Provide a skeleton with
   `TODO` holes and fixed signatures; the model writes bodies, not structure.
   Variance collapses to the body logic.
2. **From "write a project" → "write one function."** Decompose so each writer
   turn is a single self-contained unit with a *given* signature. There is no
   structure to get wrong. (Also cuts the writer phase — today 64% of tokens.)
3. **From inferred contracts → stated contracts.** The goal/plan names the exact
   files, exported symbols, and test command. Make this the default, not a
   `MU_IMPROVE_PLAN` opt-in.
4. **Make the test the spec — provide a FIXED test.** This is the strongest
   single reformulation. A given test file:
   - removes the test-harness-guessing variance (the model isn't inventing how
     to test);
   - defines success *concretely* (pass this exact assertion), so "correct" is
     no longer the model's opinion;
   - converts the task to test-driven: write impl against a fixed target.
   In the data, two whole failure families — test-isolation mistakes and
   "undefined symbol in the test" — are *test-authoring* failures that a provided
   test eliminates outright.
5. **Provide fixtures, not freedom, for everything non-essential.** Manifests,
   configs, Makefiles, directory layout: given. The model writes only the part
   under test.

The pattern: **specify everything except the one thing you are actually
measuring.** If you want to measure "can the model implement `fib()`", give it
the project, the Makefile, and the test, and ask only for `fib`'s body.

---

## 4. Worked reformulation (dojo p6-rust)

- **Current (high-variance):** "write a Rust CLI that prints the first 10
  Fibonacci numbers; use cargo." → model decides crate name, Cargo.toml, file
  layout, the algorithm, *and* how it's run. ~5 stochastic decisions; granite
  passes 0/N.
- **Minimized:** provide the cargo project (Cargo.toml + `src/main.rs` stub with
  `fn fibonacci(n: usize) -> Vec<u64> { todo!() }` and a `#[test]`), test command
  `cargo test`. Ask only for the `fibonacci` body. → 1 decision (the algorithm).
  The Cargo bad-dependency, duplicate-`use`, and binary-target reflexes become
  unnecessary because their error classes can't occur.

The reflex layer is the *recovery* for self-inflicted variance; reformulation is
*prevention*. Many existing reflexes (dependency-hygiene, build-rule-structure)
exist only because the formulation hands the model boilerplate it gets wrong.

---

## 5. The honest trade-off

Constraining the formulation **measures less of the model.** A fully fill-in-the-
blank dojo tests "can it write a function body," not "can it scaffold a project."
That is a legitimate, *deliberate* choice — but state which capability each
problem targets:

- **Capability probes** (keep open-ended): a few problems that deliberately leave
  scaffolding/structure to the model, to measure that skill — accepting high
  variance and reading them over many rounds.
- **Logic probes** (minimize): the rest pinned to a fixed plan + fixtures + test,
  so they measure implementation with low variance and few rounds.

This also fixes measurement: low-variance problems need far fewer samples to
detect a real change (the §3 reformulation makes the binary pass/fail metric
behave like the continuous one).

---

## 6. What already exists vs. what to add

**Already in place** (each a variance-killer):
- `improve-plan` spec reflexes — state some interface contracts.
- `mu dojo measure` — frozen golden plan removes planner variance for measurement.
- `MU_SEED` — pins the sampler.
- `model_profile.competence_by_toolchain` — the data to route by competence.

**To add (in priority order, by data-backed payoff):**
1. **Fixture mode**: a problem can ship a `fixtures/` dir (manifest, Makefile,
   test) copied in before the writer runs; the writer only fills stubs. Kills the
   manifest + test-authoring + build-rule classes — the bulk of granite's
   *non-degenerate* failures.
2. **Pin filenames + test command in every plan** (promote improve-plan's
   contracts to default).
3. **Competence routing**: skip/flag problems where `competence_by_toolchain`
   for the chosen model is ~0 — don't burn rounds generating noise.
4. **Single-file formulation** option for the simple problems.

---

## 7. The one-line summary

The dojo's stochasticity is mostly **self-inflicted**: we hand a weak model a
planner, an unstated contract, a blank manifest, and a multi-file layout, then
measure the noise. **Give it everything except the code under test** — pin the
plan, ship the fixtures, provide the test — and the problem space collapses from
a handful of coin flips to one, turning a 30%-pass lottery into a near-
deterministic fill-in. What remains after that is the model's *true* ceiling
(granite's degeneration), which no reflex can fix and which you should measure,
not fight.

---

## 8. Implementation: the minimization ladder

Make minimization a **declared, measurable level** per problem, not an ad-hoc
choice. Each rung removes one class of decision (and thus one variance source);
each problem states its rung, so it is clear what capability it measures.

| Level | What is given | DOF removed | Measures |
|---|---|---|---|
| **L0 open** | goal only (current) | — | scaffolding + structure + logic (max variance) |
| **L1 contract** | + exact filenames, exported symbols, test command (in PLAN.md) | structure guessing, naming | structure + logic |
| **L2 scaffold** | + manifest/Makefile/config as **fixtures** | build boilerplate | logic + test authoring |
| **L3 test-pinned** | + the **test file** as a fixture | test authoring; defines "correct" concretely | implementation only |
| **L4 fill-in** | + impl **stub** with fixed signatures | file/module structure | function bodies only (min variance) |

A problem's level is its contract with the measurement: L0–L1 are **capability
probes** (accept variance, read over many rounds); L2–L4 are **logic probes**
(low variance, few rounds). The ladder is monotone — each rung is the rung below
plus one fixture.

### 8.1 Fixture mode (the L2–L4 mechanism)

The single highest-payoff change, because it deletes the failure classes the data
ranks highest (Makefiles, manifests, test authoring).

- **Storage:** `dojo/fixtures/<problem-id>/` holds the files provided as-is
  (Makefile, `package.json`, `Cargo.toml`, the test file, stubs). Committed, like
  `dojo/golden/` already is.
- **Catalog:** `problems-catalog.json` gains per-problem
  `minimize: "L0|L1|L2|L3|L4"` and an implicit fixture set from the dir.
- **Flow:** before planning, the harness copies `dojo/fixtures/<id>/*` into the
  work dir; the planner is told these are **reference, do-not-rewrite** files
  (the existing `relevant_files_context` already supports this); the writer's
  task list is only the not-provided files. At L3 the test is fixed, so the test
  gate runs an unalterable target. At L4 the writer fills a stub against fixed
  signatures.
- **Reuse:** this is the same machinery as `mu dojo measure`'s frozen golden plan, one
  level down — there we froze the *plan*, here we freeze *files*.

### 8.2 Model-adaptive minimization (data-driven)

The level is not fixed per problem — it is **the max of the problem's floor and
what the model needs**, read from `model_profile.competence_by_toolchain`:

- competence ≳ 0.7 → run at the problem's declared level (qwen on cargo/go/clang).
- 0.2 ≤ competence < 0.7 → bump one rung (qwen on **node 0.167**, python 0.5 →
  give it the test/scaffold).
- competence ≈ 0 → either **skip** (don't burn rounds on noise) or max-scaffold
  to L4 to probe whether logic alone is reachable (granite on python/rust/go).

This couples the two levers the data demands: **routing** (skip the hopeless) and
**minimization** (scaffold the weak), both keyed off the same profile.

### 8.3 Validation — prove minimization actually cuts variance

The claim is "higher level ⇒ lower variance." Test it, don't assume it.

- **Stochasticity metric:** for a (problem, level), run N **unseeded** rounds via
  `mu dojo measure` and compute the outcome entropy / pass-rate variance. A new
  `mu dojo measure --level Lk` reports it. **Success criterion:** variance is monotone
  non-increasing in level, and L4 variance ≈ 0 for an in-competence model.
- **Seeded control:** with `MU_SEED` set, every level is already reproducible
  (5/5 identical) — that isolates the *unseeded spread* as the thing the ladder
  shrinks.
- **Capability is not lost silently:** record each problem's level in the README
  status table, so a 95%-pass number at L4 is never mistaken for a 95%-pass at
  L0. The level is part of the result.
- **Regression:** raising a problem's level must not *lower* the in-competence
  model's pass rate (a fixture must be correct); guard with one seeded run per
  fixture.

### 8.4 Sequencing (by data-backed payoff)

1. **L2 fixtures for the Makefile** on every problem that has one — deletes the
   top firing class for *both* models (`build-rule-structure`), zero capability
   loss (writing a Makefile isn't the skill under test).
2. **Competence routing** — skip granite on python/rust/go (0.0); stop measuring
   guaranteed noise.
3. **L3 test-pinned** for the python/node problems — kills the test-authoring and
   import-resolution failures that the `from main import app` and jest reflexes
   only recover from.
4. **L4 fill-in** for the simplest logic probes (p4, p6), and the
   stochasticity-metric validation that the ladder works.
5. Leave 1–2 problems at **L0** as deliberate capability probes.

The endpoint: a dojo where each problem's variance is *chosen*, the README states
each problem's level, and the residual failures are the model's true ceiling —
which is exactly what you want to measure.
