# Plan: Iteratively implement the Reflex KB (`docs/REFLEX_KB.md`)

## Context

`docs/REFLEX_KB.md` describes a queryable, probabilistic reflex knowledge base. The
**built** half exists (catalog `reflexes/registry.py`, SQLite store `reflexdb.py`,
Beta-Binomial posteriors `observe.py`, `MU_DISABLE_REFLEX` ablation in `reflexes/core.py`,
combination report + ablation shortlist, registry tests). This plan finishes the
**planned** items across **five iterations**, with Claude implementing and the user giving
go/no-go between iterations.

- **Claude implements; the local model is the feedback engine.** Claude writes the code;
  the local model (`qwen2.5-coder-7b-instruct` via LM Studio) runs the practice rounds that
  produce the feedback. The two never substitute for each other.
- **One iteration per turn.** Don't chain. After Claude finishes an iteration
  (implement + practice run + reflect + commit), **stop** and hand back to the user for
  go/no-go on the next.
- **A local practice run runs between every iteration** — mandatory, not batched. Per
  `feedback_dojo_run_config`: `MU_NUM_CTX=6000` (8192+ thrashes swap on this M2 8GB box),
  bias success over speed. It generates the feedback Claude learns from and is the
  no-regression guard.
- **Honest framing (§12 + AGENTS §5z).** The KB is observational/metadata; the runtime
  runner stays deterministic and any learned policy is baked *offline*. Of the five items
  only **chain-order baking (#4)** can move the pass rate; the **shared-core refactor (#3)**
  is behavior-preserving; the rest are metadata. For metadata items the practice run is a
  no-regression guard + feedback harvest, **not** an improvement measurement — read
  continuous metrics (repair-iters, tokens/call), never just N=5 pass/fail, and never claim
  a pass-rate gain from noise.

**Branch first** — currently on `kb-implementation` (off `main`). Commit each iteration here.

---

## Per-iteration loop (what Claude does each turn)

1. **Suggest.** Propose *one* specific improvement, grounded in the plan item **and** the
   latest feedback (prior snapshot, `CHALLENGES.md ## Open`, `dojo-failures.md` root causes,
   `mu observe` candidates). No test-specific patches; act only on signal general across ≥2
   problems (AGENTS §0).
2. **Implement.** Write the code + tests for that one item. Minimal and scoped.
3. **Verify.** `python -m mu check` and `pytest tests/ -q` green; `mu kb` rebuilds.
4. **Run the practice run (TRP).** Run it locally and harvest the feedback (recipe below).
5. **Reflect (RIP) + commit.** Walk the reflect protocol, record the snapshot into
   `docs/KB_BASELINE.md`, make the atomic commit, hand back to the user. **The loop stops**
   until the user green-lights the next iteration.

---

## Training Run Protocol (TRP) — run after every iteration

**1. Run locally** (LM Studio up, model loaded):

```sh
ROUNDS=5 MU_NUM_CTX=6000 MU_AGENT_MODEL=qwen2.5-coder-7b-instruct \
  python -m mu.dojo practice --rounds 5
```

(`--rounds 5`, not the 100 default, to bound cost. `STOP_AFTER_BARREN=5` and the 1800s
round timeout guard a stuck run.) Each round (`dojo/practice.py`): warm → `mu.dojo run`
(full problem set) → append to `dojo-failures.md` with each failure's **distilled root
cause** → refresh README DOJO-RESULTS → `mu reflect` (one *generic* lesson per failure into
`CHALLENGES.md`, or SKIP) → `mu token-report` → autocommit README/CHALLENGES/token_usage.
The reflect→CHALLENGES→planner path means later rounds in the same run adapt to earlier ones.

**2. Harvest the feedback artifacts:**

| Artifact | Command / path | Tells the reflection |
|---|---|---|
| Per-problem pass rate, worst-first | tail of `dojo-failures.md` (`per-problem summary`) | chronic vs stochastic |
| Per-round digest + **root causes** | `dojo-failures.md` round sections | raw failure evidence |
| Generic lessons | `CHALLENGES.md ## Open` | what the model generalized |
| **Candidate reflexes** (ranked signatures) | `python -m mu.observe` | the next reflex to write, if any |
| Token cost / call | `token_usage.md` | tokens/call drift (low-variance signal, §5z) |
| KB combination + ablation shortlist + profiles | `mu kb` (after rebuild) | which reflexes co-fire / are dead weight |

**3. Record the snapshot** into `docs/KB_BASELINE.md` as a dated row: pass rate, avg
repair-iters, first-try rate, tokens/call, stochasticity, top-3 `mu observe` signatures.
This is the row the next iteration compares against.

---

## Reflect-&-Improve Protocol (RIP) — run after every TRP, before handing back

Walk in order, write a findings block into `docs/KB_BASELINE.md`, check gates, propose
go/no-go:

1. **Regression check.** Did pass rate / repair-iters / tokens/call move vs the prior
   snapshot? For metadata items (#1, #2, #5) any movement beyond noise is suspect.
   For #4 a positive Δ is the goal, gated on §5z (CI excludes 0 across ≥3 seeds via
   `mu dojo measure --seed`).

   If `avg repair-iters` increases vs the prior snapshot, treat it as a regression even
   if pass rate holds — a reflex that causes the model to spin on repair is net-negative.
   Check `dojo-failures.md` for problems where repair count grew; if concentrated on one
   problem that's a single-problem effect (AGENTS §0); if spread across ≥2 it's a
   candidate to revert or gate on `--disable`.
2. **Read the model's own feedback.** Skim `CHALLENGES.md ## Open` + `dojo-failures.md`
   root causes — the model already did the generalization; start from its words.
3. **Rank candidates.** `python -m mu.observe`; the top signature that recurs ≥ `_MIN_N`=5
   **and** is deterministically fixable is the strongest candidate for the next suggestion.
4. **Propose one of:** tune the just-shipped item; add/extend a reflex *only if* a signature
   is general across ≥2 problems (never single-problem; add to `_CATALOG` + idempotency
   test + re-run TRP to confirm it fires and helps); or move on if the run is clean (the
   honest default for metadata iterations).
5. **Hand back** with the proposal. The user decides whether to re-run the TRP (if behavior
   changed) or advance.

---

## Step 0 — Record the baseline

- Create `docs/KB_BASELINE.md`. Run the **TRP** once on the untouched tree to seed the first
  snapshot row.
- `mu kb` rebuild + snapshot `report()`. Nothing downstream is measurable without this.
  **Stop and hand back** before iteration 1.

---

## Iteration 1 — Protective test harness (§11 idempotency + no-regression)

Laid down *before* the runner is touched (#3 and #4 depend on it):
- `tests/test_reflex_idempotency.py` (new): for every **scan** reflex (`trigger=='scan'`,
  `scope=='file'`) from `registry.discover()`, assert `f(f(x))==f(x)` on representative
  inputs. Registry-driven so new reflexes are auto-covered.
- Frozen no-regression smoke: known-bad fixtures → pinned expected output, so #3/#4 can't
  silently change behavior.
- **TRP → RIP.** No runtime change → pure no-regression guard + first feedback harvest.
  Note any early candidate signature for the relevant later iteration. **Stop and hand back.**

Files: `tests/test_reflex_idempotency.py`, fixtures under `tests/fixtures/`.

---

## Iteration 2 — Schema fields + automatic efficacy storage (§3 / §6 / §9)

Extend the record/DDL with curated metadata **and** close the ablation→storage loop (Δ is
measurable by hand today but never stored). Both touch `registry.py` + `reflexdb.py`, so
ship together.

*Schema fields:*
- `reflexes/registry.py`: add `artifact`, `phase`, `idempotent`, `risk`, `evidence` to
  `ReflexRecord` + `_record()`. Derive the derivable; `idempotent` is *measured* from iter-1,
  not declared. Curated fields (`artifact`, `risk`, `evidence`) via a per-reflex annotation
  map keyed by **function reference** (keep the "no name strings" discipline of `_CATALOG`).
- `reflexdb.py`: extend `_SCHEMA` `reflex` table + `_load_reflex_catalog()`; add `phase`/`ts`
  to `firing` (written by `note_fired` in `core.py`). Drop+recreate applies it.
- `tests/test_registry.py`: extend contract tests (controlled vocab, required-non-empty).

*Efficacy storage:*
- Extend `mu dojo measure` (`dojo/measure.py` / `dojo/cli.py`) so a `--disable` run emits a
  structured Δ (baseline vs disabled).
- `reflexdb.record_efficacy(reflex_id, delta, ...)` persists Δ into `reflex.efficacy`;
  surface it in `report()` / combination report. Interval via `observe.beta_binomial`;
  verdict gated on §5z (CI excludes 0 across ≥3 seeds).
- `tests/test_efficacy.py`: write/read-back + the §5z gate on synthetic Δ (no LLM).

- **TRP → RIP.** No-regression guard (storage tested offline). Reflect: does the richer
  schema expose a `risk=high` reflex the digest shows misfiring? Use the `mu kb` ablation
  shortlist to pick the first real reflex to ablate and feed a measured Δ into
  `reflex.efficacy`. **Stop and hand back.**

---

## Iteration 3 — Shared-core refactor (§5), behavior-preserving

Extract a generic core + thin `(parser, predicate)` adapters for the "one algorithm +
per-toolchain table" families:
- Start with **duplicate-declaration** (`fix_rust_duplicate_use`, `fix_js_duplicate_require`,
  `fix_csharp_duplicate_classes`). Iter-1 idempotency + frozen-output tests are the golden
  gate — output byte-identical before/after. Keep public `fix_*` names as thin wrappers
  (registry + `agent.py` call sites depend on them).
- Repeat per family only if the first lands clean.
- **TRP → RIP.** Behavior-preserving → **strict** no-regression: any metric Δ is a bug to
  chase, not a gain to keep. Also `mu dojo measure --seed 42` A/B on an affected problem for
  a tighter signal than N=5. **Stop and hand back.**

---

## Iteration 4 — Offline-baked chain order (§8) — the only real lever

**Prereq the KB undersells:** there's no central chain to order — `run_reflexes` applies
whatever list the caller passes; orders live per-language (`_MAKEFILE_REFLEXES`) and in
scattered `agent.py` call sites (`:814`, `:1309`, `apply_*_reflexes`). Two parts:
1. **Centralize** the canonical chain into a single registry-derived ordered list the
   callers consume — behavior-preserving under iter-1 tests.
2. **Bake an order** learned *offline* from the §7/§8 sequence edges + posteriors (read from
   `mu kb` on accumulated firing data) into that list as a **static constant** — never online
   sampling (preserves `MU_SEED` determinism, §8/§12).
- **TRP → RIP (the important one).** Expected to move metrics. `mu dojo measure --seed` A/B
  (old vs new order) across **≥3 seeds**, then `practice --rounds 5`. **Keep the new order
  only if Δ's CI excludes 0** (§5z); otherwise revert the order, keep the centralization.
  Record the driving sequence edges in `reflex.evidence`. **Stop and hand back.**

---

## Iteration 5 — Validation discipline + interaction model (§11 / §8 / §2)

Final layer: validation tests, the honesty audit, and the optional Bayesian interaction
model — all observational/offline, all surfacing in `mu kb report()`.

*Validation discipline:*
- `tests/test_calibration.py`: simulate known Bernoulli rates, assert `observe.beta_binomial`'s
  95% interval achieves ~95% coverage.
- `tests/test_ablation_rule.py`: encode the §5z gate ("Δ CI excludes 0 across ≥3 seeds") as a
  reusable predicate, used by iter-2's efficacy writer.
- **Honesty audit** (`mu kb` section or `tests/test_honesty_audit.py`): flag any reflex whose
  firings concentrate on a single dojo problem (AGENTS §0/§2) — observational warning.

*Interaction model (`pgmpy` optional):*
- New `reflexdb`/`observe` helper building a small Bayesian net over the `firing`
  co-occurrence + sequence data to flag interactions/contradictions; import `pgmpy` lazily,
  degrade to "install pgmpy for the interaction model" when absent.
- Add `pgmpy` to the optional/`[dev]` extra in `pyproject.toml`. Tests skip cleanly when
  absent. Strictly observational/offline (§9/§12) — never feeds the runtime runner or
  `predict.py` (§10 leak guard). Surface a `mu kb` `report()` section.

- **TRP → RIP (final).** No-regression guard. Run the audit on accumulated firings; a reflex
  tied to one problem is a generality debt to note. Flag any contradiction (a pair that
  co-fires but lowers success) as a future ablation target. Then update README problem-status
  table + Top-3 challenges (AGENTS §5a) and flip `docs/REFLEX_KB.md` status lines "planned" →
  "built". **Stop and hand back.**

---

## Verification — checked before handing back each iteration

- `python -m mu check` and `pytest tests/ -q` green; `mu kb` rebuilds and `report()` renders
  new fields/sections.
- A **TRP** ran on this machine and the **RIP** analysis is in `docs/KB_BASELINE.md` before
  the next iteration is proposed; `git diff` reviewed before the commit.
- For #2/#3/#4: `mu dojo measure --seed 42` A/B (≥3 seeds where a Δ claim is made). A re-run
  seeded `measure` gives an identical outcome (`MU_SEED` determinism guard).
- Atomic commit per iteration, `Co-Authored-By: Claude`. `docs/REFLEX_KB.md` Built/Planned
  lines and README §5a kept current as each item ships. Snapshot + go/no-go recorded in
  `docs/KB_BASELINE.md` + the commit message.

A failed gate is fixed before handing back, not papered over.

## Risks

- **#4 is the risky one** — centralizing scattered call sites can change behavior; iter-1
  golden tests are the gate, and it's revertible (keep centralization even if the learned
  order shows no Δ).
- **Metadata runs measure noise** — no-regression guards + feedback harvests; never claim a
  pass-rate gain from N=5.
- **Acting on a lucky signature** — RIP step 4 requires generality across ≥2 problems + the
  §5z gate before any reflex is added or kept (`feedback_honest_dojo`).
- **Skipping the between-iteration practice run** — mandatory; without it there's no feedback
  and no no-regression guard.
- **Practice-run cost** — `--rounds 5`, barren bail-out, seeded `measure` A/B keep it bounded.
- **pgmpy creep** — optional/lazy so core stays stdlib (§12).
