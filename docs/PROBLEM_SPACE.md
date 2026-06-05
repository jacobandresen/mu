# Minimizing the Problem Space & De-randomizing the Formulation

Where the dojo's stochasticity comes from and how to cut it — by shrinking the space
of decisions the weak model must make, and reformulating each task so fewer of those
decisions are coin flips. Grounded in the model-tagged data (granite-4.1-3b **n=34,
pass 0.33**; qwen2.5-coder-7b **n=32, pass 0.65**).

**The finding that reframes this:** with a mature reflex layer, the probabilistic
iteration found *no deterministic cause that recurs across multiple problems* — both
models' failures are dominated by writer-stalls/degeneration ("no distilled cause": 13
granite, 10 qwen) and the fixable causes are scattered n=1. The next gains are **not**
more reflexes; they are shrinking what we ask the model to decide.

> **A correction worth stating** (it shaped the plan): `build-rule-structure` has the
> top *firing* rate for both models (granite 1.44, qwen 1.19 firings/session), but
> firings are the Makefile reflexes **winning**, not failing — a session has one
> outcome, so a >1 rate can't be a failure rate. So "fixture away the Makefile" is
> **not** the top lever (it would delete a class the reflexes already handle). The real
> residue is degeneration (the model ceiling) and planner variance.

---

## 1. Where the variance comes from (ranked by evidence)

Every independent decision the model makes under sampling is a stochastic variable:

1. **The planner — dominant.** A fresh plan each run (decomposition, file names, test
   command) changes everything downstream. Demonstrated: `mu dojo measure` runs a
   problem from a *frozen* plan and gets byte-identical results (5/5 with `MU_SEED`),
   whereas the same problem live swings pass↔stall round to round.
2. **Inferred structure (guessing the contract).** When the goal doesn't state the
   interface, the model invents filenames and exported symbols — each a gamble (p7-flask's
   recurring `undefined name 'app'`; the `from main import app` resolver exists *only
   because* filenames are unpinned).
3. **Degenerate generation (the model ceiling).** Weak models loop or stall — ~13 of 21
   granite failures distill to "no cause." This is variance you cannot reflex away.
4. **Cross-file coupling.** Multi-file tasks add an import/symbol-resolution failure
   class (test↔impl, p7/p8) and the p10 multi-project ceiling.
5. **Out-of-competence routing.** Granite is **0.0 on python/rust/go** (n=34); running
   it there is pure noise.

The throughline: **most variance is *self-inflicted by the formulation*, not intrinsic
to coding.** The planner, the unstated contract, and the multi-file coupling are
decisions we *handed* to a stochastic weak model. Take the decision back and the
variance disappears. (Boilerplate the model writes wrong — manifests, Makefiles — is
mostly already taken back by the reflex layer; fixtures help only where a reflex can't,
e.g. a Cargo.toml the model invents bad deps for.)

---

## 2. The levers — constrain the degrees of freedom

| Lever | DOF removed | Status |
|---|---|---|
| **Pin the plan** (golden plan; model writes code, not structure) | planner | `mu dojo measure` (shipped) |
| **Provide manifest/config/test as a fixture** | boilerplate the model invents | fixture mode (shipped; `dojo/fixtures/<id>/`) |
| **Pin exact filenames + test command** | naming | `improve-plan` spec reflexes (partial) |
| **Collapse to one file / fixed layout** | cross-file coupling | not yet |
| **Route by competence** | out-of-competence noise | `mu dojo run --route` (shipped) |

Combined, these turn a problem from "make N independent stochastic bets" into "make
1–2" — the difference between a 30%-pass coin-flip and a near-deterministic fill-in.

---

## 3. Shifting the formulation — turn inferred decisions into givens

The pattern: **specify everything except the one thing you are actually measuring.** To
measure "can the model implement `fib()`", give it the project, the Makefile, and the
test, and ask only for `fib`'s body. Concretely:

- **"build an app" → "fill in the blanks":** a skeleton with `TODO` holes and fixed
  signatures; variance collapses to the body logic.
- **inferred contracts → stated contracts:** the plan names the exact files, symbols,
  and test command (default, not opt-in).
- **Make the test the spec — provide a FIXED test.** The strongest single reformulation:
  it removes test-harness-guessing variance and defines "correct" concretely (pass this
  assertion). Two whole failure families — test-isolation mistakes and "undefined symbol
  in the test" — are *test-authoring* failures a provided test eliminates outright.

---

## 4. The honest trade-off

Constraining the formulation **measures less of the model**: a fill-in-the-blank problem
tests "can it write a function body," not "can it scaffold a project." That's a
legitimate, *deliberate* choice — but state which capability each problem targets:

- **Capability probes** (keep open-ended): a few problems that leave scaffolding to the
  model, read over many rounds, accepting high variance.
- **Logic probes** (minimize): the rest pinned to plan + fixtures + test, low variance,
  few rounds.

This also fixes measurement: low-variance problems need far fewer samples to detect a
real change. The level must be recorded in the README status table, so a 95%-pass number
at L4 is never mistaken for 95%-pass at L0 — the level is part of the result.

---

## 5. The minimization ladder

Minimization is a **declared, measurable level** per problem (`problems-catalog.json`
`minimize: "L0"…"L4"`), not an ad-hoc choice. Each rung is the rung below plus one
fixture; each problem states what capability it measures.

> **Status:** the `minimize` field exists in the catalog but is **not yet read by any
> code** — it's a declared intent. What runs today is the generic mechanism below
> (copy a problem's `dojo/fixtures/<id>/*`, regardless of level) plus competence
> *skip*; the level is descriptive, not enforced.

| Level | What is given | Measures |
|---|---|---|
| **L0 open** | goal only (current default) | scaffolding + structure + logic (max variance) |
| **L1 contract** | + exact filenames, symbols, test command in PLAN.md | structure + logic |
| **L2 scaffold** | + manifest/Makefile/config as **fixtures** | logic + test authoring |
| **L3 test-pinned** | + the **test file** as a fixture | implementation only |
| **L4 fill-in** | + impl **stub** with fixed signatures | function bodies only (min variance) |

**Fixture mode (the L2–L4 mechanism, shipped):** `dojo/fixtures/<problem-id>/` holds
files provided as-is (committed like `dojo/golden/`). Before the writer runs, the harness
copies them into the work dir and marks their task done, so the writer only fills the
not-provided files — a given file can't be written wrong, so its whole failure class
disappears. Same machinery as `mu dojo measure`'s frozen plan, one level down: there we
freeze the *plan*, here we freeze *files*. First fixture: `dojo/fixtures/p6-rust/Cargo.toml`.

**Model-adaptive (data-driven), partly built:** the intent is that the effective level
is the max of the problem's floor and what the model needs, read from
`model_profile.competence_by_toolchain` — run at the declared level where competence
≳0.7; **bump a rung** where 0.2–0.7 (qwen on node 0.167); **skip** where ≈0. Today only
the **skip** end is implemented (`fixtures.should_skip_problem`, `mu dojo run --route`);
the auto-bump is planned.

**Validation (shipped):** `mu dojo measure` reports a **stochasticity** metric
(`1 − modal/N` over unseeded runs). The claim "higher level ⇒ lower variance" is tested,
not assumed: variance should be monotone non-increasing in level, ≈0 at L4 for an
in-competence model. Raising a level must not *lower* the in-competence pass rate (a
fixture must be correct) — guard with one seeded run per fixture.

---

## 6. One-line summary

The dojo's stochasticity is mostly **self-inflicted**: we hand a weak model a planner,
an unstated contract, and a multi-file layout, then measure the noise. **Give it
everything except the code under test** — pin the plan, ship the fixtures, provide the
test — and the problem space collapses from a handful of coin flips to one. What remains
is the model's *true* ceiling (granite's degeneration), which no reflex can fix and which
you should measure, not fight.
