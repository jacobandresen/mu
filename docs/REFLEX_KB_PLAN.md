# Plan: Iteratively implement the Reflex KB (`docs/REFLEX_KB.md`)

## Context

`docs/REFLEX_KB.md` describes a queryable, probabilistic reflex knowledge base. The
**built** half exists (catalog `reflexes/registry.py`, SQLite store `reflexdb.py`,
Beta-Binomial posteriors `observe.py`, `MU_DISABLE_REFLEX` ablation in `reflexes/core.py`,
combination report + ablation shortlist, registry tests). This plan finishes the six
**planned** items, **one per iteration**.

**This plan is executed one iteration at a time by `pi-dev`.** `pi-dev` is the `pi`
executable running a **cloud-model** coding setup — it is the implementing agent. Each
iteration it **suggests the concrete improvement, implements it, runs the tests, runs a
local practice run, and reflects on the feedback** before the iteration is considered done.
Claude's role is **supervisor, not implementer** — Claude does the *minimal* amount of work:
dispatch the next iteration to `pi`, review what it produced against the gates below, approve
or send it back, and only step in directly when `pi-dev` is genuinely stuck. **Claude does
not write the implementation; `pi-dev` does.**

Two distinct models are in play, and the split matters: `pi-dev` (cloud, via `pi`) **writes
the code**; the **local** model (`qwen2.5-coder-7b-instruct` via LM Studio) **runs the
practice rounds** that generate the feedback. The cloud implementer never replaces the local
feedback engine.

**One iteration per turn.** Do **not** chain iterations. After `pi-dev` finishes an
iteration (implementation + local practice run + reflection + commit), **stop** and surface
the result to the user/supervisor for go/no-go on the *next* iteration. The whole point is
that Claude supervises a sequence of small, independently-reviewed steps rather than running
the plan end to end.

**A local practice run happens between every iteration.** This is not optional and not
batched: after `pi-dev` implements iteration *N* and before iteration *N+1* begins, a full
local-model practice run (`python -m mu.dojo practice`) must run locally on this machine
(per `feedback_dojo_run_config`: `qwen2.5-coder-7b-instruct`, `MU_NUM_CTX=6000` — 8192+
thrashes swap on this M2 8GB box — bias success over speed).
That run *generates the feedback `pi-dev` learns from* — failures, distilled root causes,
generic lessons, token costs, candidate-reflex signatures — and is the no-regression guard.

**The local model does the heavy lifting of *discovery*.** Each practice round the local
model runs the whole problem set and produces the feedback. `pi-dev`'s job between rounds is
to **read that feedback and turn the clearest, most general signal into the next
improvement** — never a test-specific patch (`feedback_honest_dojo`, AGENTS §0). Claude's
job is to confirm `pi-dev` did exactly that and nothing more.

**Honest framing (per §12 + AGENTS §5z).** The KB is observational/metadata by design —
the runtime runner stays deterministic; any learned policy is baked *offline*. So of the
six items only **chain-order baking (#4)** can move the pass rate, and the **shared-core
refactor (#3)** is behavior-preserving. For the four metadata items the practice run is a
**no-regression guard + a feedback harvest**, not an improvement measurement. Read
continuous metrics (repair-iters, tokens/call), never just N=5 pass/fail, and never
over-claim a gain from noise. The supervisor enforces this — if `pi-dev` claims a pass-rate
gain from a metadata iteration, send it back.

**Branch first** — currently on `kb-implementation` (already created off `main`). `pi-dev`
commits each iteration onto this branch.

---

## Roles

| Role | Who | Does |
|---|---|---|
| **Implementer** | `pi-dev` (`pi` CLI, cloud model) | Suggests the iteration's improvement, writes the code/tests, runs the local practice run, reflects, commits. |
| **Feedback engine** | local model (`qwen2.5-coder-7b-instruct`) | Runs the practice rounds that produce failures, root causes, lessons, candidate signatures. |
| **Supervisor** | Claude | Dispatches one iteration to `pi`, reviews the diff + practice feedback against the gates, approves/rejects, stops. Writes no implementation. |

### Claude's minimal-work contract (read this literally)

**Claude does the least possible work. `pi-dev` does everything else.** The default for any
unit of work in this plan is "`pi-dev` does it." Claude acts only when supervision *requires*
it. Concretely:

**Claude DOES (and nothing beyond this):**
- Dispatch exactly **one** iteration to `pi` per turn, then stop.
- Read `pi-dev`'s returned diff, practice snapshot, and reflection.
- Check it against the gates in **Verification** and the honesty rules.
- Say **approve** (advance) or **send back** (with the one specific reason), then stop.
- Record nothing of its own beyond a one-line go/no-go; `pi-dev` writes the artifacts.

**Claude DOES NOT (these are `pi-dev`'s job — never do them for it):**
- Write or edit implementation code, tests, fixtures, or docs.
- Run the practice run, `mu check`, `pytest`, `mu kb`, `mu observe`, or `mu dojo measure`.
- Write the `docs/KB_BASELINE.md` snapshot or the commit.
- Fix a failing gate. A failed gate is **sent back to `pi-dev`**, not repaired by Claude.
- Design the iteration's improvement. `pi-dev` suggests it; Claude only judges it.

**The one escape hatch:** Claude steps in directly *only* when `pi-dev` is genuinely and
repeatedly stuck (e.g. it cannot run the `pi` CLI at all, or it has failed the same gate
twice with no progress). Even then, Claude does the **minimum** unblocking action and hands
control straight back. "Faster if I just do it" is **not** a reason to do it — minimizing
Claude's work is an explicit goal of this plan, not a fallback.

The handoff each iteration is: **Claude → `pi-dev`** (dispatch via `pi`: "implement iteration N per the plan;
suggest the specific improvement, then build it, then run the local practice run, then
reflect"); **`pi-dev` → Claude** (diff + practice snapshot + reflection + proposed commit);
**Claude → user** (go/no-go on iteration N+1).

---

## Per-iteration loop (what `pi-dev` does each turn)

Every iteration below follows the same five-step loop. Claude assigns it; `pi-dev` runs it.

1. **Suggest.** `pi-dev` proposes the *specific* improvement for this iteration — grounded
   in the plan item **and** the most recent practice feedback (the prior iteration's
   snapshot, `CHALLENGES.md ## Open`, `dojo-failures.md` root causes, `mu observe`
   candidates). One concrete change, justified.
2. **Implement.** `pi-dev` writes the code + tests for that one item. Keeps it minimal and
   scoped; no test-specific patches.
3. **Verify locally.** `python -m mu check` and `pytest tests/ -q` green. `mu kb` rebuilds.
4. **Run the local practice run (TRP).** Between this iteration and the next, `pi-dev` runs
   the practice run locally and harvests the feedback artifacts (recipe below).
5. **Reflect (RIP) + commit.** `pi-dev` walks the reflect protocol, records the snapshot
   into `docs/KB_BASELINE.md`, makes the atomic commit, and hands the result back to Claude.
   **Then the loop stops** until the supervisor green-lights the next iteration.

---

## The Training Run Protocol (TRP) — `pi-dev` runs this locally after every iteration

The single, reusable recipe each iteration invokes between itself and the next. The local
model is the engine; everything below is "let it run locally, then collect what it produced."

**1. Run locally.** From the repo root on this machine, with LM Studio up and the model
loaded:

```sh
ROUNDS=5 MU_NUM_CTX=6000 MU_AGENT_MODEL=qwen2.5-coder-7b-instruct \
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

## The Reflect-&-Improve Protocol (RIP) — `pi-dev` runs this after every TRP, before handing back

Explicit reflection between runs. `pi-dev` walks these in order, writes a findings block into
`docs/KB_BASELINE.md`, checks the gates, and proposes go/no-go for the next item. Claude
reviews that proposal.

1. **Regression check.** Did pass rate / avg repair-iters / tokens/call move vs the prior
   snapshot? For metadata items (#1,#2,#3,#6,#7) *any* movement beyond noise is suspect —
   investigate before proceeding. For #4 a positive Δ is the goal; gate on §5z (CI excludes
   0 across ≥3 seeds via `mu dojo measure --seed`).
2. **Read the model's own feedback.** Skim the new `CHALLENGES.md ## Open` lessons and the
   `dojo-failures.md` root causes. The model already did the generalization work — start
   from its words.
3. **Rank candidate improvements.** Run `python -m mu.observe`; the top failure-cause
   *signature* that (a) recurs ≥ the `_MIN_N`=5 threshold and (b) is deterministically
   fixable is the strongest candidate for the *next* iteration's suggestion.
4. **Propose — one of:**
   - **Tune the just-shipped item** (e.g. the schema-derived `idempotent` flag was wrong
     for reflex X; the centralized chain order mis-sequenced A before B).
   - **Add/extend a reflex** *only if* a signature is clearly general across ≥2 problems
     (honesty audit, AGENTS §0/§2 — never single-problem). New reflex → add to `_CATALOG`,
     write its idempotency test, re-run TRP to confirm it fires and helps.
   - **Move on** if the run is clean and no general signal emerged (the honest default for
     metadata iterations).
5. **Hand back.** `pi-dev` stops here with a proposal. The supervisor decides whether to
   re-run the TRP (if behavior changed) or advance to the next iteration.

This loop is the heart of the plan: the local model surfaces the failures, `pi-dev` converts
the general ones into deterministic fixes, the local practice run measures whether that
helped, and Claude keeps the whole thing honest and minimal.

---

## Step 0 — Record the baseline (gate for every later comparison)

`pi-dev`:
- Create `docs/KB_BASELINE.md`. Run the **TRP** once locally on the untouched tree to seed
  the first snapshot row (pass rate, repair-iters, tokens/call, top candidate signatures).
- `mu kb` rebuild + snapshot `report()`.
- Nothing downstream is measurable without this reference. **Stop and hand back** before
  iteration 1.

---

## Iteration 1 — Protective test harness (§11 idempotency + no-regression)

Protection laid down *before* the runner is touched (refactor #3 and chain-order #4 depend
on it). `pi-dev` suggests the exact fixture set, then implements:
- `tests/test_reflex_idempotency.py` (new): for every **scan** reflex
  (`trigger=='scan'`, `scope=='file'`) from `registry.discover()`, assert `f(f(x))==f(x)`
  on representative inputs. Registry-driven so new reflexes are auto-covered.
- Frozen no-regression smoke: known-bad fixtures → pinned expected output, so #3/#4 can't
  silently change behavior.
- **Local practice run (TRP) → RIP.** No runtime change → run is a pure no-regression guard
  + first real feedback harvest. Reflect: is any candidate signature already strong enough
  to act on early? Note it for the relevant later iteration. **Stop and hand back.**

Files: `tests/test_reflex_idempotency.py`, fixtures under `tests/fixtures/`.

---

## Iteration 2 — Curated schema fields (§3 / §6)

Add `artifact`, `phase`, `idempotent`, `risk`, `evidence` to the record + DDL, plus
`firing.phase` / `firing.ts`. `pi-dev` suggests the controlled vocab, then implements:
- `reflexes/registry.py`: extend `ReflexRecord` + `_record()`. Derive the derivable;
  `idempotent` is *measured* from iter-1, not declared. Curated fields (`artifact`, `risk`,
  `evidence`) via a per-reflex annotation map keyed by **function reference** (keep the "no
  name strings" discipline of `_CATALOG`).
- `reflexdb.py`: extend `_SCHEMA` `reflex` table + `_load_reflex_catalog()`; add
  `phase`/`ts` to `firing` (written by `note_fired` in `core.py`). Drop+recreate applies it.
- `tests/test_registry.py`: extend contract tests (controlled vocab, required-non-empty).
- **Local practice run (TRP) → RIP.** No runtime change → no-regression guard. Reflect: does
  the richer schema expose a reflex with `risk=high` that the digest shows misfiring? If so,
  that's the iter-tune candidate. **Stop and hand back.**

---

## Iteration 3 — Write `reflex.efficacy` automatically (§9 / §3)

Close the ablation→storage loop (today Δ is measurable by hand but never stored). `pi-dev`
suggests the Δ schema, then implements:
- Extend `mu dojo measure` (`dojo/measure.py` / `dojo/cli.py`) so a `--disable` run emits a
  structured Δ (baseline vs disabled).
- `reflexdb.record_efficacy(reflex_id, delta, ...)` persists Δ into `reflex.efficacy`;
  surface it in `report()` / combination report. Interval via `observe.beta_binomial`;
  verdict gated on §5z (CI excludes 0 across ≥3 seeds).
- `tests/test_efficacy.py`: write/read-back + the §5z gate on synthetic Δ (no LLM).
- **Local practice run (TRP) → RIP.** Storage is unit-tested offline; the practice run is the
  no-regression guard. Reflect: use the `mu kb` **ablation shortlist** from the harvest to
  pick the first real reflex to ablate next — feed a measured Δ into `reflex.efficacy` for
  it. **Stop and hand back.**

---

## Iteration 4 — Shared-core refactor (§5), behavior-preserving

Extract a generic core + thin `(parser, predicate)` adapters for the three "one algorithm +
per-toolchain table" families. `pi-dev` suggests the first family, then implements:
- Start with **duplicate-declaration** (`fix_rust_duplicate_use`, `fix_js_duplicate_require`,
  `fix_csharp_duplicate_classes`). Iter-1 idempotency + frozen-output tests are the golden
  gate — output byte-identical before/after. Keep public `fix_*` names as thin wrappers
  (registry + `agent.py` call sites depend on them).
- Repeat per family only if the first lands clean.
- **Local practice run (TRP) → RIP.** Behavior-preserving → **strict** no-regression: any
  metric Δ is a bug to chase, not an improvement to keep. Also `mu dojo measure --seed 42`
  A/B on an affected problem for a tighter signal than N=5 practice. **Stop and hand back.**

---

## Iteration 5 — Offline-baked chain order (§8) — the only real lever

**Prereq the KB undersells:** there is no central chain to order — `run_reflexes` applies
whatever list the caller passes; orders live per-language (`_MAKEFILE_REFLEXES`) and in
scattered `agent.py` call sites (`:814`, `:1309`, `apply_*_reflexes`). `pi-dev` suggests the
canonical chain, then implements two parts:
1. **Centralize** the canonical chain into a single registry-derived ordered list the
   callers consume — behavior-preserving under iter-1 tests.
2. **Bake an order** learned *offline* from the §7/§8 sequence edges + posteriors (read out
   of `mu kb` on the accumulated firing data) into that list as a **static constant** —
   never online sampling (preserves `MU_SEED` determinism, §8/§12).
- **Local practice run (TRP) → RIP (the important one).** This is the step expected to move
  metrics. Measure `mu dojo measure --seed` A/B (old vs new order) across **≥3 seeds**, then
  the `practice --rounds 5` run. **Keep the new order only if Δ's CI excludes 0** (§5z);
  otherwise revert the order, keep the centralization. Reflect on the sequence edges that
  drove the chosen order and record the evidence in `reflex.evidence`. **Stop and hand back.**

---

## Iteration 6 — Remaining validation discipline (§11)

`pi-dev` suggests the calibration test design, then implements:
- `tests/test_calibration.py`: simulate known Bernoulli rates, assert
  `observe.beta_binomial`'s 95% interval achieves ~95% coverage.
- `tests/test_ablation_rule.py`: encode the §5z gate ("Δ CI excludes 0 across ≥3 seeds") as
  a reusable predicate, used by iter-3's efficacy writer.
- **Honesty audit** (a `mu kb` section or `tests/test_honesty_audit.py`): flag any reflex
  whose firings concentrate on a single dojo problem (AGENTS §0/§2) — observational warning.
- **Local practice run (TRP) → RIP.** No runtime change → no-regression guard. Reflect: run
  the new honesty audit on the accumulated firings; if it flags a reflex tied to one
  problem, that's a generality debt to note (not necessarily fix now). **Stop and hand back.**

---

## Iteration 7 — Bayesian net for interactions/contradictions (§8 / §2), `pgmpy` optional

`pi-dev` suggests the net structure, then implements:
- New `reflexdb`/`observe` helper building a small Bayesian net over the `firing`
  co-occurrence + sequence data to flag interactions/contradictions; import `pgmpy` lazily,
  degrade to "install pgmpy for the interaction model" when absent.
- Add `pgmpy` to the optional/`[dev]` extra in `pyproject.toml`. Tests skip cleanly when
  absent. Strictly observational/offline (§9/§12) — never feeds the runtime runner or
  `predict.py` (§10 leak guard). Surface a `mu kb` `report()` section.
- **Local practice run (TRP) → RIP (final).** No runtime change → no-regression guard.
  Reflect on any contradiction the net flags (a pair that co-fires but lowers success) as a
  future ablation target. Then update README problem-status table + Top-3 challenges
  (AGENTS §5a) and flip `docs/REFLEX_KB.md` status lines "planned" → "built". **Stop and
  hand back.**

---

## Verification (per iteration + final) — what the supervisor checks before approving

For each iteration, Claude confirms `pi-dev` produced:
- `python -m mu check` and `pytest tests/ -q` green.
- `mu kb` rebuilds; `report()` renders the new fields/sections.
- A **local practice run (TRP)** ran on this machine and the **RIP** analysis is recorded in
  `docs/KB_BASELINE.md` before the next iteration is proposed; gates re-checked; `git diff`
  reviewed before the commit.
- For #3/#4/#5 also `mu dojo measure --seed 42` A/B (≥3 seeds where a Δ claim is made).
- Determinism guard: a re-run seeded `measure` gives an identical outcome (`MU_SEED`).
- An atomic commit per iteration, `Co-Authored-By: Claude`. `docs/REFLEX_KB.md` Built/Planned
  lines and README §5a kept current as each item ships.
- The snapshot and the go/no-go recorded in `docs/KB_BASELINE.md` + the commit message.

If any check is missing or a gate fails, the supervisor sends the iteration back to `pi-dev`
rather than fixing it directly.

## Risks

- **#4 is the risky one** — centralizing scattered call sites can change behavior; iter-1
  golden tests are the gate, and it's revertible (keep centralization even if the learned
  order shows no Δ).
- **Metadata runs measure noise** — framed as no-regression guards + feedback harvests;
  never over-claim a pass-rate gain from N=5. The supervisor rejects any such claim.
- **Acting on a lucky signature** — RIP step 4 requires generality across ≥2 problems and
  the §5z gate before any reflex is added or kept (`feedback_honest_dojo`).
- **Skipping the between-iteration practice run** — the local run is mandatory between every
  iteration; without it there is no feedback to reflect on and no no-regression guard.
- **Practice-run cost** — `--rounds 5` (not 100), barren bail-out, and seeded `measure` A/B
  keep the local-model time bounded.
- **Supervisor scope creep** — Claude reviews and gates; it does not implement. Keeping
  Claude's work minimal is itself a goal of this plan.
- **pgmpy creep** — optional/lazy so core stays stdlib (§12).
