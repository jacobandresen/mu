# Reflex Knowledge Base — Design & Reference

Status: **partially implemented.** Goal: turn ~80 ad-hoc reflexes into a queryable,
de-duplicated knowledge base and reason **probabilistically** about which reflexes
(and combinations) help — without overclaiming from confounded data.

- **Built:** catalog + miner + model profiles (`reflexes/registry.py`, `reflexdb.py`,
  via `mu kb`); the Beta-Binomial posterior (`observe.py`); the completeness check
  (`registry.unregistered()`); the **ablation mechanism** (§9 — `MU_DISABLE_REFLEX`,
  `mu dojo measure --disable`); the **combination report + ablation shortlist** (§7, in
  `mu kb`); the `summary` schema field; registry-contract tests (§11).
- **Planned:** *writing* `reflex.efficacy` automatically (the mechanism lets you measure
  Δ by hand; nothing stores it), the remaining curated schema fields (§3:
  `artifact`/`phase`/`idempotent`/`risk`/`evidence`), the shared-core refactor (§5), and
  model-in-the-loop validation (§11). Marked inline.

---

## 1. Motivation

Reflexes (`src/mu/reflexes/`) are deterministic condition→action fixers, discovered one
at a time from dojo failures, grouped by language, chained to a fixpoint by
`run_reflexes`. The KB adds machine-readable metadata to answer: what exists / overlaps
(inventory), which reflexes actually move the pass rate (efficacy), and which work as a
bundle or contradict (combination). It is **observational by construction**; the causal
arbiter is `mu dojo measure` ablation (§9) — the KB *ranks hypotheses*, ablation
*confirms*. Non-goal: feeding firing data into the plan-time `predict.py` (would leak the
label — §10).

---

## 2. Architecture

```
session archive (~/.mu/sessions/*)         # source of truth
        │  mine logs
        ▼
~/.mu/mu.db  (SQLite, rebuildable via `mu kb`)
   ├── reflex / session / firing / model_profile          [built]
        ├── Beta-Binomial posteriors (observe.py, §8)      [built]
        ├── combination report + ablation shortlist (§7)   [built, in mu kb]
        └── ablation: MU_DISABLE_REFLEX + measure --disable [built]
              → write Δ into reflex.efficacy               [planned]
```

`sqlite3` + `math` are stdlib; `scipy`/`pgmpy` are optional, gated like `scikit-learn`.
Layers depend one way — mining (facts) → SQL aggregation (counts) → probability (beliefs)
→ ablation (truth); none reaches back up.

---

## 3. Characterising a reflex — the schema

One row per reflex; the `reflex` table and registry record *are* the per-reflex docs.
**Built today** are the rows marked *(built)*; the rest are the intended schema, not yet
populated.

| Attribute | Type / vocabulary | Status |
|---|---|---|
| `id` | text PK — function name | built |
| `toolchain` | python·rust·go·csharp·js·makefile·cargo·npm·dotnet·`*` | built |
| `error_class` | controlled vocab (§4) | built |
| `trigger` | scan·lint-out·test-out·project·plan | built |
| `scope` | file·project | built |
| `summary` | one line (first docstring line) | built |
| `efficacy` | Δ pass-rate from ablation (§9) | column exists, **never written** |
| `artifact`·`phase`·`idempotent`·`risk`·`evidence` | curated | planned |

`registry.py` builds the *(built)* fields straight from the function objects (id from
`__name__`, toolchain from `__module__`, trigger from `inspect.signature`).

---

## 4. Grouping — two orthogonal axes

**Physical** by toolchain (the modules, for code locality); **semantic** by `error_class`
— the cross-language lens:

| `error_class` | members (cross-toolchain) |
|---|---|
| dependency-hygiene | `fix_rust_cargo_bad_dependency`, `fix_requirements_stdlib_entries`, `fix_package_json_builtin_deps`, … |
| duplicate-declaration | `fix_rust_duplicate_use`, `fix_js_duplicate_require`, `fix_csharp_duplicate_classes`, … |
| missing-symbol-import | `fix_python_undefined_imports`, `fix_js_missing_requires`, `fix_go_missing_pkg_imports`, `fix_csharp_missing_using`, … |
| test-isolation | `fix_sqlite_test_isolation`, `fix_missing_flask_client_fixture`, `fix_jest_fs_mock`, … |
| test-command-correctness | `fix_makefile_bare_pytest`/`bare_vitest`, `fix_package_json_bare_jest`, blocking-`./binary`→`go test` |
| brace/paren-balance | `fix_json_unclosed_brackets`, `fix_csharp_missing_braces`, `fix_rust_unbalanced_braces`, … |
| syntax-artifact | `fix_tool_call_artifacts`, `fix_literal_newlines`, `fix_csharp_verbatim_string_escape`, … |
| build-rule-structure | the Makefile target/recipe/tab family |

(The live, exhaustive list is `mu kb`'s catalog section.)

---

## 5. Sharing reflexes across toolchains *(planned)*

Several semantic groups are *one algorithm + a per-toolchain table* (dependency-hygiene,
duplicate-declaration, missing-symbol-import). The planned target — not yet done, the
reflexes are still per-language copies — is a **generic core + thin adapter** (a new
toolchain = add `(parser, predicate)`). The `error_class` field makes each such family
visible, so the refactor target is obvious; it would be behaviour-preserving, gated by
golden tests.

---

## 6. SQLite store — DDL

The actual schema today (`reflexdb._SCHEMA`). The curated §3 columns and `firing.phase`/
`ts` are planned, not in this DDL.

```sql
CREATE TABLE reflex (
  id TEXT PRIMARY KEY, toolchain TEXT, error_class TEXT,
  trigger TEXT, scope TEXT, summary TEXT, efficacy REAL  -- efficacy: null until ablated (§9)
);
CREATE TABLE session (
  session_id TEXT PRIMARY KEY, problem_id TEXT, model TEXT, model_family TEXT,
  outcome TEXT, success INT, repair_iters INT, first_try INT,
  tasks_total INT, prompt_tokens INT, ts TEXT
);
CREATE TABLE firing (
  session_id TEXT, reflex_id TEXT, file TEXT, pass_index INT,
  FOREIGN KEY(session_id) REFERENCES session(session_id)
);
CREATE TABLE model_profile (             -- per-model aggregates (docs/MODELS.md)
  model_family TEXT PRIMARY KEY, n_sessions INT, pass_rate REAL, pass_lo REAL,
  pass_hi REAL, first_try_rate REAL, avg_repair_iters REAL,
  competence_by_toolchain TEXT, error_class_propensity TEXT, updated TEXT
);
```

`firing` is the heart: `pass_index` gives sequence, the session join gives the outcome,
self-joins give co-occurrence. The DB is **rebuildable** (`mu kb`), never the source of
truth — so `build()` drops + recreates, and a schema change just applies.

---

## 7. Combination analysis

Emitted by `mu kb` (`reflexdb.combination_report`) over the `firing` table: per-reflex
**conditional success** `P(✓ | reflex)` (interval-aware via §8, so small-N reads
"insufficient data"), **co-occurrence** pairs, **sequence** edges (A fires on an earlier
pass than B), and an **ablation shortlist** — reflexes that fire enough (n≥5) but whose
interval still contains the base rate, so their effect isn't distinguishable; most-fired
first, with the `--disable` command. Observational — a ranking of hypotheses to ablate
(§9), never a causal claim.

---

## 8. Probabilistic reasoning

Raw rates lie at small N — model the uncertainty (`observe.beta_binomial`, built). Each
outcome is Bernoulli with a `Beta(α₀,β₀)` prior centred on the base rate `r̄` (weak,
~2 pseudo-observations); after `s` successes / `f` failures the posterior mean is
`(α₀+s)/(α₀+β₀+s+f)` with a 95% credible interval (scipy if present, else normal approx).
**Rank by posterior mean *and* interval width:** a combo at 3/3 with a wide interval ranks
below 40/50 with a tight one — the honest fix for the "lucky 5/5" trap.

Planned uses of the posterior: offline-learning a fixed chain order baked into the runner
(never online sampling — that would break `MU_SEED` reproducibility; today `run_reflexes`
uses a static catalog order), and a small Bayesian net for interactions/contradictions
(`pgmpy` optional).

---

## 9. Causality guard — ablation is the arbiter

Firing data is **observational and confounded** (a reflex fires *because* the model
erred), so the probabilistic layer only **proposes**; causation comes from ablation.

**Mechanism (built).** `run_reflexes` honors `MU_DISABLE_REFLEX` (comma-separated reflex
`__name__`s), skipping exactly those fixers (`tests/test_reflex_ablation.py` pins it). Run
an ablation by measuring a **frozen, seeded** baseline twice and reading the Δ:

```sh
mu dojo measure p8-node-todo --runs 5 --seed 42                          # baseline
mu dojo measure p8-node-todo --runs 5 --seed 42 --disable fix_js_duplicate_require
```

If the pass rate drops, the reflex was load-bearing. If the change is negligible across
seeds, it is dead weight.

**Ordering (built).** `mu kb`'s ablation shortlist (§7) uses the §8 posteriors to choose
which reflexes to ablate first.

**Planned.** Storing the measured Δ automatically in `reflex.efficacy`.

---

## 10. Relationship to the existing predictor

- `predict.py` (sklearn): `P(success)` from **plan-time** features — leak-free,
  prospective, feeds the planner.
- Reflex KB (this): `P(fix | reflexes)` from **runtime** firings — confounded,
  exploratory, used to bundle reflexes and prioritise ablations.

They must stay separate: reflex firings must never enter the plan-time predictor (the
firing happened *because* of the eventual outcome).

---

## 11. Validation discipline

The suite has started (`tests/`); the model-in-the-loop parts remain the intended
discipline, not yet automated.

- **Completeness (built):** `tests/test_registry.py` — `registry.unregistered()` empty
  (every public `fix_*`/`apply_*` cataloged), every reflex has a summary, derived
  `trigger`/`scope` ∈ controlled sets, ids unique.
- **Ablation hook (built):** `tests/test_reflex_ablation.py`; **combination report
  (built):** `tests/test_combination_report.py`.
- **Planned (model-in-the-loop):** idempotency `f(f(x))==f(x)` per scan reflex;
  interval-calibration (simulate known rates, assert 95% coverage); the **ablation rule**
  — any "helps / dead weight" claim promoted to code must clear a Δ whose credible
  interval excludes 0 across ≥3 seeds, never one lucky round (AGENTS §5z); no-regression
  on the frozen-baseline suite; and an honesty audit flagging any reflex tied to a single
  dojo problem (AGENTS §0/§2).

---

## 12. Risks & honest caveats

- **Confounding:** observational firing data can't prove causation — §9 ablation is the
  sole source of `efficacy`; the probabilistic layer is hypothesis generation.
- **Small N:** many reflexes fire rarely — Beta-Binomial shrinkage + interval-aware
  ranking; never act on a point rate.
- **Determinism:** any learned policy is baked **offline**; the runtime runner stays
  deterministic so `MU_SEED` reproducibility holds.
- **Dependency creep:** core is stdlib; `scipy`/`pgmpy` optional.
