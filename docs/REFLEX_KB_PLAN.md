# Plan: Iteratively implement the Reflex KB (`docs/REFLEX_KB.md`)

## Context

`docs/REFLEX_KB.md` describes a queryable, probabilistic reflex knowledge base. The
**built** half exists (catalog `reflexes/registry.py`, SQLite store `reflexdb.py`,
Beta-Binomial posteriors `observe.py`, `MU_DISABLE_REFLEX` ablation in `reflexes/core.py`,
combination report + ablation shortlist, registry tests). This plan finishes the six
**planned** items, **one per iteration**, and the *entire plan is executed end to end* —
implement an item, then run a full local-model **training run** (`mu dojo practice`), then
**reflect** on the feedback that run collected before starting the next item.

**The local model does the heavy lifting.** Each practice round, the local model (per
`feedback_dojo_run_config`: `qwen3:8b`, `MU_NUM_CTX=8192`, bias success over speed) runs
the whole problem set and *generates the feedback we learn from* — failures, distilled root
causes, generic lessons, token costs, candidate-reflex signatures. My job between rounds is
to **read that feedback and turn the clearest, most general signal into the next
improvement** — never a test-specific patch (`feedback_honest_dojo`, AGENTS §0).

**Honest framing (per §12 + AGENTS §5z).** The KB is observational/metadata by design —
the runtime runner stays deterministic; any learned policy is baked *offline*. So of the
six items only **chain-order baking (#4)** can move the pass rate, and the **shared-core
refactor (#3)** is behavior-preserving. For the four metadata items the training run is a
**no-regression guard + a feedback harvest**, not an improvement measurement. I read
continuous metrics (repair-iters, tokens/call), never just N=5 pass/fail, and never
over-claim a gain from noise.

**Branch first** — currently on `main`. Create `kb-implementation` before any edits.

This plan is executed end to end by a **single model** — the same executor implements each
item, runs its training run, reflects, gates, and commits before moving on.

---

## The Training Run Protocol (TRP) — run after every iteration

The single, reusable recipe each iteration invokes. The local model is the engine here;
everything below is "let it run, then collect what it produced."

**1. Run.** From the repo root, with LM Studio up and the model loaded:

```sh
ROUNDS=5 MU_NUM_CTX=8192 MU_AGENT_MODEL=qwen3:8b \
  python -m mu.dojo practice --rounds 5
```

(`--rounds 5`, not the 100 default, to bound cost. `STOP_AFTER_BARREN=5` and the 1800s
round timeout already guard a stuck run. Preflight checks LM Studio is reachable.)

What each round does for us automatically (`dojo/practice.py`): warm → `mu.dojo run` (full
problem set) → append the round to `dojo-failures.md` with each failure's **distilled root
cause** → refresh the README DOJO-RESULTS block → `mu reflect` (distill one *generic*
lesson per failure into `CHALLENGES.md`, or SKIP) → `mu token-report` → autocommit
README/CHALLENGES/token_usage. The reflect→CHALLENGES→planner path means later rounds in
the *same* run already adapt to earlier failures — the model is learning within the run.

**2. Harvest the feedback artifacts** (this is the point of the run):

| Artifact | Command / path | What it tells the reflection |
|---|---|---|
| Per-problem pass rate, worst-first | tail of `dojo-failures.md` (`per-problem summary`) | which problems are chronic vs stochastic |
| Per-round digest + **root causes** | `dojo-failures.md` round sections | the raw failure evidence |
| Generic lessons | `CHALLENGES.md` `## Open` | what the model itself generalized |
| **Candidate reflexes** (ranked failure-cause signatures) | `python -m mu.observe` | the next reflex to write, if any |
| Token cost / call | `token_usage.md` | tokens/call drift (a real, low-variance signal, §5z) |
| KB combination + ablation shortlist + model profiles | `mu kb` (after `mu kb` rebuild) | which reflexes co-fire / are dead weight |

**3. Record the snapshot** into `docs/KB_BASELINE.md` as a dated row: pass rate, avg
repair-iters, first-try rate, tokens/call, stochasticity, and the top-3 candidate
signatures from `mu observe`. This is the row the *next* iteration compares against.

---

## The Reflect-&-Improve Protocol (RIP) — run after every TRP, before the next item

Explicit reflection between runs. Walk these in order, write a findings block into
`docs/KB_BASELINE.md`, check the gates, and decide go/no-go before the next item:

1. **Regression check.** Did pass rate / avg repair-iters / tokens/call move vs the prior
   snapshot? For metadata items (#1,#2,#3,#6,#7) *any* movement beyond noise is suspect —
   investigate before proceeding. For #4 a positive Δ is the goal; gate on §5z (CI excludes
   0 across ≥3 seeds via `mu dojo measure --seed`).
2. **Read the model's own feedback.** Skim the new `CHALLENGES.md ## Open` lessons and the
   `dojo-failures.md` root causes. The model already did the generalization work — start
   from its words.
3. **Rank candidate improvements.** Run `python -m mu.observe`; the top failure-cause
   *signature* that (a) recurs ≥ the `_MIN_N`=5 threshold and (b) is deterministically
   fixable is the strongest candidate for a new/extended reflex.
4. **Decide — one of:**
   - **Tune the just-shipped item** (e.g. the schema-derived `idempotent` flag was wrong
     for reflex X; the centralized chain order mis-sequenced A before B).
   - **Add/extend a reflex** *only if* a signature is clearly general across ≥2 problems
     (honesty audit, AGENTS §0/§2 — never single-problem). New reflex → add to `_CATALOG`,
     write its idempotency test, re-run TRP to confirm it fires and helps.
   - **Move on** if the run is clean and no general signal emerged (the honest default for
     metadata iterations).
5. **Re-run TRP** if the decision changed runtime behavior; otherwise proceed.

This loop is the heart of the plan: the local model surfaces the failures, I convert the
general ones into deterministic fixes, and the next run measures whether that helped.

---

## Step 0 — Record the baseline (gate for every later comparison)

- Create `docs/KB_BASELINE.md`. Run the **TRP** once on the untouched tree to seed the
  first snapshot row (pass rate, repair-iters, tokens/call, top candidate signatures).
- `mu kb` rebuild + snapshot `report()`.
- Nothing downstream is measurable without this reference.

---

## Iteration 1 — Protective test harness (§11 idempotency + no-regression)

Protection laid down *before* the runner is touched (refactor #3 and chain-order #4 depend
on it).
- `tests/test_reflex_idempotency.py` (new): for every **scan** reflex
  (`trigger=='scan'`, `scope=='file'`) from `registry.discover()`, assert `f(f(x))==f(x)`
  on representative inputs. Registry-driven so new reflexes are auto-covered.
- Frozen no-regression smoke: known-bad fixtures → pinned expected output, so #3/#4 can't
  silently change behavior.
- **TRP → RIP.** No runtime change → run is a pure no-regression guard + first real
  feedback harvest. Reflect: is any candidate signature already strong enough to act on
  early? Note it for the relevant later iteration.

Files: `tests/test_reflex_idempotency.py`, fixtures under `tests/fixtures/`.

---

## Iteration 2 — Curated schema fields (§3 / §6)

Add `artifact`, `phase`, `idempotent`, `risk`, `evidence` to the record + DDL, plus
`firing.phase` / `firing.ts`.
- `reflexes/registry.py`: extend `ReflexRecord` + `_record()`. Derive the derivable;
  `idempotent` is *measured* from iter-1, not declared. Curated fields (`artifact`, `risk`,
  `evidence`) via a per-reflex annotation map keyed by **function reference** (keep the "no
  name strings" discipline of `_CATALOG`).
- `reflexdb.py`: extend `_SCHEMA` `reflex` table + `_load_reflex_catalog()`; add
  `phase`/`ts` to `firing` (written by `note_fired` in `core.py`). Drop+recreate applies it.
- `tests/test_registry.py`: extend contract tests (controlled vocab, required-non-empty).
- **TRP → RIP.** No runtime change → no-regression guard. Reflect: does the richer schema
  expose a reflex with `risk=high` that the digest shows misfiring? If so, that's the
  iter-tune candidate.

---

## Iteration 3 — Write `reflex.efficacy` automatically (§9 / §3)

Close the ablation→storage loop (today Δ is measurable by hand but never stored).
- Extend `mu dojo measure` (`dojo/measure.py` / `dojo/cli.py`) so a `--disable` run emits a
  structured Δ (baseline vs disabled).
- `reflexdb.record_efficacy(reflex_id, delta, ...)` persists Δ into `reflex.efficacy`;
  surface it in `report()` / combination report. Interval via `observe.beta_binomial`;
  verdict gated on §5z (CI excludes 0 across ≥3 seeds).
- `tests/test_efficacy.py`: write/read-back + the §5z gate on synthetic Δ (no LLM).
- **TRP → RIP.** Storage is unit-tested offline; the practice run is the no-regression
  guard. Reflect: use the `mu kb` **ablation shortlist** from the harvest to pick the first
  real reflex to ablate next — feed a measured Δ into `reflex.efficacy` for it.

---

## Iteration 4 — Shared-core refactor (§5), behavior-preserving

Extract a generic core + thin `(parser, predicate)` adapters for the three "one algorithm +
per-toolchain table" families.
- Start with **duplicate-declaration** (`fix_rust_duplicate_use`, `fix_js_duplicate_require`,
  `fix_csharp_duplicate_classes`). Iter-1 idempotency + frozen-output tests are the golden
  gate — output byte-identical before/after. Keep public `fix_*` names as thin wrappers
  (registry + `agent.py` call sites depend on them).
- Repeat per family only if the first lands clean.
- **TRP → RIP.** Behavior-preserving → **strict** no-regression: any metric Δ is a bug to
  chase, not an improvement to keep. Also `mu dojo measure --seed 42` A/B on an affected
  problem for a tighter signal than N=5 practice.

---

## Iteration 5 — Offline-baked chain order (§8) — the only real lever

**Prereq the KB undersells:** there is no central chain to order — `run_reflexes` applies
whatever list the caller passes; orders live per-language (`_MAKEFILE_REFLEXES`) and in
scattered `agent.py` call sites (`:814`, `:1309`, `apply_*_reflexes`). Two parts:
1. **Centralize** the canonical chain into a single registry-derived ordered list the
   callers consume — behavior-preserving under iter-1 tests.
2. **Bake an order** learned *offline* from the §7/§8 sequence edges + posteriors (read out
   of `mu kb` on the accumulated firing data) into that list as a **static constant** —
   never online sampling (preserves `MU_SEED` determinism, §8/§12).
- **TRP → RIP (the important one).** This is the step expected to move metrics. Measure
  `mu dojo measure --seed` A/B (old vs new order) across **≥3 seeds**, then the
  `practice --rounds 5` run. **Keep the new order only if Δ's CI excludes 0** (§5z);
  otherwise revert the order, keep the centralization. Reflect on the sequence edges that
  drove the chosen order and record the evidence in `reflex.evidence`.

---

## Iteration 6 — Remaining validation discipline (§11)

- `tests/test_calibration.py`: simulate known Bernoulli rates, assert
  `observe.beta_binomial`'s 95% interval achieves ~95% coverage.
- `tests/test_ablation_rule.py`: encode the §5z gate ("Δ CI excludes 0 across ≥3 seeds") as
  a reusable predicate, used by iter-3's efficacy writer.
- **Honesty audit** (a `mu kb` section or `tests/test_honesty_audit.py`): flag any reflex
  whose firings concentrate on a single dojo problem (AGENTS §0/§2) — observational warning.
- **TRP → RIP.** No runtime change → no-regression guard. Reflect: run the new honesty
  audit on the accumulated firings; if it flags a reflex tied to one problem, that's a
  generality debt to note (not necessarily fix now).

---

## Iteration 7 — Bayesian net for interactions/contradictions (§8 / §2), `pgmpy` optional

- New `reflexdb`/`observe` helper building a small Bayesian net over the `firing`
  co-occurrence + sequence data to flag interactions/contradictions; import `pgmpy` lazily,
  degrade to "install pgmpy for the interaction model" when absent.
- Add `pgmpy` to the optional/`[dev]` extra in `pyproject.toml`. Tests skip cleanly when
  absent. Strictly observational/offline (§9/§12) — never feeds the runtime runner or
  `predict.py` (§10 leak guard). Surface a `mu kb` `report()` section.
- **TRP → RIP (final).** No runtime change → no-regression guard. Reflect on any
  contradiction the net flags (a pair that co-fires but lowers success) as a future
  ablation target. Then update README problem-status table + Top-3 challenges (AGENTS §5a)
  and flip `docs/REFLEX_KB.md` status lines "planned" → "built".

---

## Verification (per iteration + final)

- `python -m mu check` and `pytest tests/ -q` green after every iteration.
- `mu kb` rebuilds; `report()` renders the new fields/sections.
- **TRP after every iteration and the RIP analysis before the next**; re-check the gates and
  review the `git diff` before committing. The snapshot and the go/no-go are recorded in
  `docs/KB_BASELINE.md` + the commit message.
- For #3/#4/#5 also `mu dojo measure --seed 42` A/B (≥3 seeds where a Δ claim is made).
- Determinism guard: re-run a seeded `measure`, expect an identical outcome (`MU_SEED`).
- Atomic commit per iteration, `Co-Authored-By: Claude`. `docs/REFLEX_KB.md` Built/Planned
  lines and README §5a kept current as each item ships.

## Risks

- **#4 is the risky one** — centralizing scattered call sites can change behavior; iter-1
  golden tests are the gate, and it's revertible (keep centralization even if the learned
  order shows no Δ).
- **Metadata runs measure noise** — framed as no-regression guards + feedback harvests;
  never over-claim a pass-rate gain from N=5.
- **Acting on a lucky signature** — RIP step 4 requires generality across ≥2 problems and
  the §5z gate before any reflex is added or kept (`feedback_honest_dojo`).
- **Practice-run cost** — `--rounds 5` (not 100), barren bail-out, and seeded `measure` A/B
  keep the local-model time bounded.
- **pgmpy creep** — optional/lazy so core stays stdlib (§12).
