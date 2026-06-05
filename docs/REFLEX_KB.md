# Reflex Knowledge Base — Design & Implementation Plan

Status: proposal. Owner: mu maintainers.
Goal: turn ~80 ad-hoc reflexes into a queryable, analyzable, de-duplicated
knowledge base, and reason **probabilistically** about which reflexes (and
combinations) actually help — without overclaiming from confounded data.

---

## 1. Motivation

Reflexes (`src/mu/reflexes/`) are deterministic condition→action fixers,
discovered one at a time from dojo failures, grouped physically by language, and
chained to a fixpoint by `run_reflexes`. There is no machine-readable metadata,
so we cannot answer:

- **Inventory:** what exists, what overlaps, what generalises across toolchains?
- **Efficacy:** which reflexes actually move the pass rate, and which fire but
  never matter (dead weight)?
- **Combination:** which reflexes work as a bundle; which contradict; in what
  order should the chain run?

The KB answers these. It is **observational and exploratory by construction**;
the causal arbiter remains `measure.sh` ablation (§9). The KB *ranks hypotheses*;
ablation *confirms* them.

Non-goals: feeding reflex-firing data into the plan-time `predict.py` (would
leak the label — see §10); online/random reflex selection (would break the
reproducibility `MU_SEED` exists to guarantee).

---

## 2. Architecture

```
session archive (~/.mu/sessions/*)         # source of truth (existing)
        │  mine logs
        ▼
~/.mu/reflexes.db  (SQLite, rebuildable)    # Phase 1–2
   ├── reflex   (static KB, from @reflex registry)
   ├── session  (outcome labels)
   └── firing   (one row per reflex application)
        │
        ├── mu reflex-stats        # SQL co-occurrence / conditional report (Phase 2)
        ├── reflex_prob.py         # Beta-Binomial posteriors, CPTs (Phase 3)
        └── ablation (MU_DISABLE_REFLEX + measure.sh) → writes causal efficacy (Phase 4)
```

Dependency posture: `sqlite3` is stdlib (the same store the dojo tests use). The
probabilistic core is ~30 lines of stdlib math. `scipy.stats` / `pgmpy` are
**optional** upgrades, gated like `scikit-learn` already is in `predict.py`.

---

## 3. Characterising a reflex — the schema

One row per reflex. Every field is derivable from code or cheap to curate.

| Attribute | Type / vocabulary | Source |
|---|---|---|
| `id` | text PK — function name | code |
| `summary` | text — one line | docstring |
| `toolchain` | python·rust·go·csharp·js·makefile·cargo·npm·dotnet·`*` | module |
| `artifact` | source·manifest·makefile·plan·test-config | code |
| `error_class` | controlled vocab (§4) | curated |
| `trigger` | scan·lint-out·test-out·project·plan | **function signature** |
| `phase` | write·lint-repair·test-repair·pre-flight·plan | call site |
| `idempotent` | bool | verified by test (§11.1) |
| `scope` | file·project·multi-file | signature |
| `risk` | syntactic-safe·heuristic·intent-reconstruction | curated |
| `evidence` | dojo problem + cause + commit that surfaced it | git/CHALLENGES |
| `efficacy` | Δ pass-rate from ablation (null until measured) | §9 |

Mechanism: a `@reflex(...)` decorator registers metadata at import into a module
registry; `reflexdb.py` upserts it into the `reflex` table. No behaviour change.

---

## 4. Grouping — two orthogonal axes

- **Physical:** by toolchain (the modules). Keep for code locality.
- **Semantic:** by `error_class` — the cross-language lens. Grounded in the real
  inventory:

| `error_class` | members (cross-toolchain) |
|---|---|
| dependency-hygiene | `fix_rust_cargo_bad_dependency`, `fix_requirements_stdlib_entries`, `fix_requirements_path_entries`, `fix_package_json_builtin_deps`, `fix_makefile_pip_install_empty` |
| duplicate-declaration | `fix_rust_duplicate_use`, `fix_js_duplicate_require`, `fix_csharp_duplicate_classes`, `fix_duplicate_var` |
| missing-symbol-import | `fix_python_undefined_imports`, `fix_python_missing_project_imports`, `fix_js_missing_requires`, `fix_go_missing_pkg_imports`, `fix_csharp_missing_using`, `fix_rust_missing_trait_import` |
| unused-import | `fix_go_unused_imports`, `py_autofix` |
| test-isolation | `fix_sqlite_test_isolation`, `fix_sqlite_memory_multi_connect`, `fix_missing_flask_client_fixture`, `fix_jest_fs_mock` |
| test-command-correctness | `fix_makefile_bare_pytest`/`bare_vitest`/`pytest_in_non_python`, `fix_package_json_bare_jest`, blocking-`./binary`→`go test` |
| brace/paren-balance | `fix_json_unclosed_brackets`, `fix_csharp_missing_braces`, `fix_js_extra_closing_brace`, `fix_rust_unbalanced_braces`, `fix_missing_close_paren` |
| syntax-artifact | `fix_tool_call_artifacts`, `fix_literal_newlines`, `fix_makefile_literal_*`, `fix_csharp_verbatim_string_escape` |
| build-rule-structure | the Makefile target/recipe/tab family |

---

## 5. Sharing reflexes across toolchains

The semantic groups show several families are *one algorithm + a per-toolchain
table*. Refactor each to **generic core + thin adapter**:

- dependency-hygiene → `strip_manifest_deps(manifest, parse, forbidden_pred)`;
  adapters: Cargo (invalid semver), requirements.txt (stdlib), package.json
  (node builtins). New toolchain = add `(parser, predicate)`.
- duplicate-declaration → `dedupe_top_level_decls(text, decl_regex)`; adapter =
  per-language regex.
- missing-symbol-import → `resolve_undefined(names, sibling_sources, fmt_import)`;
  adapter = name extractor + import formatter.

The KB's `error_class` field makes each family **visible**, so the refactor
target is obvious and a new language inherits mature logic. Refactors are
behaviour-preserving and gated by the §11 golden tests.

---

## 6. SQLite store — DDL

```sql
CREATE TABLE reflex (
  id TEXT PRIMARY KEY, summary TEXT, toolchain TEXT, artifact TEXT,
  error_class TEXT, trigger TEXT, phase TEXT, idempotent INT,
  scope TEXT, risk TEXT, evidence TEXT, efficacy REAL  -- null until ablated
);
CREATE TABLE session (
  session_id TEXT PRIMARY KEY, problem_id TEXT, model TEXT,
  outcome TEXT, success INT, repair_iters INT, first_try INT,
  prompt_tokens INT, ts TEXT
);
CREATE TABLE firing (
  session_id TEXT, reflex_id TEXT, file TEXT,
  pass_index INT, phase TEXT, ts TEXT,
  FOREIGN KEY(session_id) REFERENCES session(session_id),
  FOREIGN KEY(reflex_id)  REFERENCES reflex(id)
);
CREATE INDEX firing_session ON firing(session_id);
CREATE INDEX firing_reflex  ON firing(reflex_id);
```

`firing` is the heart: `pass_index` gives sequence, the session join gives the
outcome, self-joins give co-occurrence. The DB is **rebuildable** from the
archive (`reflexdb.py --rebuild`), so it is never the source of truth.

---

## 7. Combination analysis — pure SQL

```sql
-- co-occurrence (pair counts)
SELECT a.reflex_id, b.reflex_id, COUNT(DISTINCT a.session_id) n
FROM firing a JOIN firing b
  ON a.session_id=b.session_id AND a.reflex_id < b.reflex_id
GROUP BY 1,2 ORDER BY n DESC;

-- conditional success: P(success | reflex)
SELECT f.reflex_id,
       AVG(s.success) p_success, COUNT(*) n
FROM firing f JOIN session s USING(session_id)
GROUP BY 1 ORDER BY n DESC;

-- sequence: "A enables B" (A fires on an earlier pass than B)
SELECT a.reflex_id before_, b.reflex_id after_, COUNT(*) n
FROM firing a JOIN firing b
  ON a.session_id=b.session_id AND a.pass_index < b.pass_index
GROUP BY 1,2 ORDER BY n DESC;
```

Lift = `P(A,B)/(P(A)·P(B))`. Synergy = `P(✓|A,B) > max(P(✓|A),P(✓|B))`;
antagonism (a contradiction signal) = the reverse.

---

## 8. Probabilistic reasoning

Raw rates lie at small N. Model the uncertainty.

### 8.1 Beta-Binomial conditional success (the core)

Each reflex/combo's fix outcome is Bernoulli with a `Beta(α₀,β₀)` prior centred
on the base success rate `r̄` (e.g. `α₀=2r̄`, `β₀=2(1−r̄)` — a weak prior worth
~2 pseudo-observations). After `s` successes / `f` failures:

```
α = α₀ + s,  β = β₀ + f
P̂(✓ | reflexes) = α / (α+β)                 # posterior mean, shrinks small-N → r̄
Var = αβ / ((α+β)²(α+β+1))
95% credible interval = Beta(α,β).ppf([.025,.975])   # scipy optional; else normal approx
```

Rank by **posterior mean *and* interval width**: a combo at 3/3 with a wide
interval ranks below 40/50 with a tight one. This is the honest fix for the
"lucky 5/5" trap.

### 8.2 Bayesian network / CPTs (interactions + contradictions)

A small DAG `problem-features → error_class → {reflexes fired} → outcome` with
CPTs estimated (same smoothing) from SQLite counts. Captures what pairwise lift
cannot:

- **interaction:** "reflex B raises P(fix) only when A also fired";
- **learned contradiction:** "A∧B lowers P(fix)" — complements the runner's
  cycle guard.

Hand-rolled CPTs keep it dependency-free; `pgmpy` is an optional upgrade.

### 8.3 The decision question

Given a file failing with error signature E, *which reflex set maximises
P(fixed)?* = `argmax_S P(fixed | S, E)` from the posterior. Use it to
**offline-learn a fixed chain order** (highest-posterior-first), baked into the
runner — *not* online sampling (which would reintroduce non-determinism). A
Markov view (state = error-class, transition = reflex) yields the same
"most-likely-to-resolve-next" ranking.

---

## 9. Causality guard — ablation is the arbiter

Firing data is **observational and confounded**: a reflex fires *because* the
model erred, so `P(✓|A)` is entangled with problem difficulty, and any success
model leaks. Therefore the probabilistic layer **proposes**; it never concludes.

Causal test: `MU_DISABLE_REFLEX=<id>` (read by `run_reflexes`) on a **frozen,
seeded** baseline (`measure.sh`, §`MU_SEED`), re-measure, read Δ pass-rate and
Δ repair-iters. That Δ — not the posterior — is written into `reflex.efficacy`.
The posteriors merely **order which ablations to run first**.

---

## 10. Relationship to the existing predictor

- `predict.py` (sklearn): `P(success)` from **plan-time** features — leak-free,
  prospective, feeds the planner.
- Reflex KB (this): `P(fix | reflexes)` from **runtime** firings — confounded,
  exploratory, used to bundle reflexes and prioritise ablations.

They are different stages and must stay separate: reflex firings must never enter
the plan-time predictor (the firing happened *because* of the eventual outcome).

---

## 11. Implementation phases & deliverables

Each phase is independently shippable and independently tested (§12).

**Phase 1 — registry + store.**
- `@reflex(...)` decorator + `reflexes/registry.py` (in-memory dict).
- `reflexdb.py`: create schema, upsert `reflex` rows from the registry, mine
  `session`/`firing` from `~/.mu/sessions/*` logs.
- `mu reflexes [--family X|--json]` lists/queries; `mu reflexdb --rebuild`.

**Phase 2 — SQL combination report.**
- `mu reflex-stats`: emit the §7 queries as a Markdown report
  (`reflex_stats.md`): fire-counts, co-occurrence/lift, conditional success,
  sequence edges.

**Phase 3 — probabilistic module.**
- `reflex_prob.py`: Beta-Binomial posteriors + credible intervals over reflexes
  and top combos; ranked **bundle candidates** and **drop candidates** (high
  fire-count, posterior ≈ base rate). CPT/Bayesian-net optional.

**Phase 4 — ablation loop.**
- `MU_DISABLE_REFLEX` honoured in `run_reflexes`; `measure.sh --disable <id>`
  writes `reflex.efficacy`. Posteriors choose the ablation order.

**Phase 5 — shared-core refactor (§5),** guided by the empirical clusters,
behaviour-preserving.

---

## 12. Validation & testing — how we know it works

The KB's value proposition is concrete and therefore **testable end-to-end**:
*it should let us drop dead reflexes and bundle/order helpful ones, confirmed by
measurement.* Each layer has its own gate, and the whole thing has an
integration test that closes the loop.

### 12.1 Registry & schema (Phase 1) — unit tests
- **Completeness:** every public `fix_*`/`apply_*` in `reflexes/` is registered
  with all required fields non-null. (Test walks the package, asserts coverage —
  fails CI when someone adds a reflex without metadata.)
- **Vocabulary:** `error_class`, `trigger`, `phase`, `risk` ∈ controlled sets.
- **Trigger consistency:** declared `trigger` matches the function signature
  (e.g. a `lint-out` reflex must accept a `lint_error` arg) — derived and
  cross-checked automatically.
- **Idempotency:** for each `scan` reflex with a recorded fixture, applying it
  twice equals applying it once (`f(f(x)) == f(x)`). This is a real correctness
  property the fixpoint runner depends on; the test makes it a contract.
- **JSON round-trip:** registry → `reflexes.json` → reload is identity.

### 12.2 Miner (Phase 1) — fixture & reconciliation tests
- **Golden log fixture:** a synthetic session log with known `Reflex: …` lines →
  assert the exact `firing` rows produced (parser correctness).
- **Rebuild idempotency:** `--rebuild` twice yields an identical DB (checksum).
- **Reconciliation:** row counts in `firing`/`session` match an independent
  `grep -c` over the same archive subset (no double-count, no drop).
- **Schema integrity:** foreign-key checks pass (`PRAGMA foreign_key_check`).

### 12.3 Probabilistic layer (Phase 3) — math & calibration tests
- **Math correctness:** posterior mean/interval on hand-worked inputs
  (e.g. s=8,f=2 with `Beta(1,1)` → mean 0.75) match to 1e-9.
- **Shrinkage behaviour:** with `s=f=0`, posterior mean == base rate; as N grows,
  posterior → empirical rate (assert monotone convergence on simulated data).
- **Credible-interval calibration (the key statistical test):** simulate K
  reflexes with *known* true success probabilities, draw N Bernoulli outcomes
  each, build 95% intervals; assert empirical coverage ∈ [0.93, 0.97] over many
  trials. A miscalibrated estimator fails here.
- **Ranking sanity:** a 3/3 reflex must rank *below* a 40/50 reflex (interval
  width tie-break) — guards against the lucky-small-N trap by construction.
- **CPT recovery (if built):** generate synthetic data from a known 3-node net
  with a planted interaction; assert the estimated CPTs recover it within
  tolerance.

### 12.4 Ablation = the causal validation (Phase 4)
This is where "effectiveness" is actually proven, deterministically:
- **Disable plumbing:** unit-test that `MU_DISABLE_REFLEX=fix_X` makes
  `run_reflexes` skip `fix_X` (and only it).
- **Reproducibility precondition:** with `MU_SEED` set, the same problem from a
  frozen golden plan yields byte-identical runs (already demonstrated). Ablation
  experiments inherit this — the Δ they measure is signal, not noise.
- **Drop-candidate test:** take a reflex the posteriors flag as "fires often,
  posterior ≈ base rate." Ablate it across all relevant frozen baselines (N
  seeds). **Success criterion:** Δ pass-rate ≈ 0 and Δ repair-iters ≈ 0 within
  noise → confirmed dead weight → remove it (and re-run the suite to confirm no
  regression). If Δ < 0, it was *not* dead — the KB was wrong, keep it. Either
  way the KB's claim is *tested*, not trusted.
- **Helpful-reflex test (the positive control):** re-run the
  `fix_js_duplicate_require` experiment as a regression fixture — disable it on
  the frozen p8 baseline and confirm the duplicate-`fs` SyntaxError returns
  (5/5), enable it and confirm that error is gone (5/5). This pins a known
  causal effect as a permanent test.
- **Bundle/order test:** reorder the chain per the learned sequence on a frozen
  baseline; **success criterion:** the fixpoint converges in ≤ the current number
  of passes on every problem, with pass-rate unchanged or better. Reject any
  reorder that increases passes or lowers pass rate.

### 12.5 End-to-end / meta-validation
- **Closed-loop test:** on a fixed snapshot of the session archive, the pipeline
  (mine → posteriors → pick top drop-candidate → ablate → write efficacy) runs
  to completion and produces a non-empty, schema-valid `reflex.efficacy` for at
  least one reflex. Run in CI against a committed mini-archive fixture so it is
  deterministic and offline (no model needed).
- **Statistical guardrail against overfitting:** any "this reflex/combo helps"
  claim promoted to a code change must clear an ablation Δ whose **credible
  interval excludes 0** across ≥3 seeds — not a single lucky round. This is the
  written embodiment of the project's anti-noise discipline (AGENTS §5z).
- **Honesty audit:** a periodic check that every reflex still passes the
  general-class test (AGENTS §0/§2) — the KB surfaces any reflex whose `evidence`
  ties it to exactly one dojo problem and whose pattern is problem-specific, for
  human review.

### 12.6 Success metrics for the KB as a whole
- **Coverage:** 100% of reflexes registered (CI-enforced).
- **Actionability:** ≥1 confirmed drop (dead reflex removed) and ≥1 confirmed
  bundle/order improvement, each validated by ablation with interval-excludes-0.
- **No regression:** after any KB-driven change, the full frozen-baseline suite
  (`measure.sh` over all problems × ≥3 seeds) shows pass-rate non-decreasing.
- **Maintenance cost:** adding a reflex requires only the `@reflex` decorator;
  the completeness test enforces it.

---

## 13. Risks & honest caveats

- **Confounding:** observational firing data cannot prove causation. Mitigated by
  §9 ablation as the sole source of the `efficacy` field. The probabilistic layer
  is explicitly labelled "hypothesis generation."
- **Small N:** many reflexes fire rarely. Mitigated by Beta-Binomial shrinkage
  and interval-aware ranking; never act on a point rate.
- **Determinism:** all learned policy (chain order) is baked **offline**; the
  runtime runner stays deterministic so `MU_SEED` reproducibility holds.
- **Dependency creep:** core is stdlib (`sqlite3`, `math`); `scipy`/`pgmpy` are
  optional, gated like `scikit-learn`.
