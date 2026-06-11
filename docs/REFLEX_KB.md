# Reflex Knowledge Base — Design & Reference

## 1. Motivation

Reflexes (`src/mu/reflexes/`) are deterministic condition→action fixers chained
to a fixpoint by `run_reflexes`. The KB adds machine-readable metadata to answer:
what exists / overlaps (inventory), which reflexes move the pass rate (efficacy),
and which work as a bundle or contradict (combination). **Observational by
construction** — the causal arbiter is `mu dojo measure` ablation (§9), which the
KB ranks hypotheses for. Non-goal: feeding firing data into `predict.py` (would
leak the label — §10).

---

## 2. Architecture

```
session archive (~/.mu/sessions/*)
        │  mine logs
        ▼
~/.mu/mu.db  (SQLite, rebuildable via `mu kb`)
   ├── reflex / session / firing / efficacy_run / model_profile
   ├── Beta-Binomial posteriors (observe.py, §8)
   ├── combination report + ablation shortlist (§7)
   ├── ablation: MU_DISABLE_REFLEX + measure --disable + record_efficacy()
   └── [planned] shared-core refactor, baked chain order, interaction model
```

`sqlite3` + `math` are stdlib; `scipy` optional (exact Beta quantiles); `pgmpy` required for interaction model. Layers depend one way
— mining → aggregation → probability → ablation; none reaches back up.

---

## 3. Schema

One row per reflex; the `reflex` table and `ReflexRecord` are the per-reflex docs.

| Attribute | Type / vocabulary | Status |
|---|---|---|
| `id` | function `__name__` | built |
| `toolchain` | python·rust·go·csharp·javascript·makefile·core·plan | built |
| `error_class` | controlled vocab (§4) | built |
| `trigger` | scan·lint-out·test-out·project·plan | built |
| `scope` | file·project | built |
| `summary` | first docstring line | built |
| `phase` | write·repair·plan (derived from trigger) | built |
| `artifact` | file type (py·rs·Makefile·json·…; None = unspecified; curated) | built |
| `idempotent` | True/False/None — measured by double-apply test | built |
| `risk` | low·medium·high (curated) | built |
| `evidence` | dojo problem id(s) that motivated this reflex (curated) | built |
| `efficacy` | mean Δ pass-rate from ≥3 ablation seeds | built (populated by `record_efficacy()`) |

`registry.py` derives `id`/`toolchain`/`trigger`/`scope`/`phase` from the function
object; curated fields come from `_ANNOTATIONS` (keyed by function reference, not
name string). `idempotent` is populated from `idempotent_ids.txt`, which the
`test_idempotent_ids_committed` test keeps honest.

---

## 4. Grouping — two orthogonal axes

**Physical** by toolchain (module locality); **semantic** by `error_class`:

| `error_class` | cross-toolchain members (examples) |
|---|---|
| dependency-hygiene | `fix_rust_cargo_bad_dependency`, `fix_requirements_stdlib_entries`, `fix_package_json_builtin_deps` |
| duplicate-declaration | `fix_rust_duplicate_use`, `fix_js_duplicate_require`, `fix_csharp_duplicate_classes` |
| missing-symbol-import | `fix_python_undefined_imports`, `fix_js_missing_requires`, `fix_go_missing_pkg_imports`, `fix_csharp_missing_using` |
| test-isolation | `fix_sqlite_test_isolation`, `fix_missing_flask_client_fixture`, `fix_jest_fs_mock` |
| test-command-correctness | `fix_makefile_bare_pytest`/`bare_vitest`, `fix_package_json_bare_jest` |
| brace-paren-balance | `fix_json_unclosed_brackets`, `fix_csharp_missing_braces`, `fix_rust_unbalanced_braces` |
| syntax-artifact | `fix_tool_call_artifacts`, `fix_literal_newlines`, `fix_csharp_verbatim_string_escape` |
| build-rule-structure | the Makefile target/recipe/tab family |

Live exhaustive list: `mu kb` catalog section.

---

## 5. Sharing reflexes across toolchains

Several semantic groups are *one algorithm + a per-toolchain table*
(duplicate-declaration, missing-symbol-import, dependency-hygiene). Built as
generic core + thin `(parser, predicate)` adapters (`_fix_duplicate_decls` in
`core.py`); composite-chain functions for C#/JS/Rust.

---

## 6. SQLite store

Schema lives in `reflexdb._SCHEMA`; the DB is rebuildable (`mu kb`), never the
source of truth. The `firing` table is the heart: `pass_index` gives sequence
(0 = write pass, >0 = repair), the session join gives the outcome, self-joins give
co-occurrence. `efficacy_run` stores per-seed ablation measurements and is
preserved across rebuilds.

---

## 7. Combination analysis

`mu kb` (`reflexdb.combination_report`) over `firing`: per-reflex conditional
success `P(✓ | reflex)` (interval-aware via §8), co-occurrence pairs, sequence
edges, and an ablation shortlist — reflexes that fire enough but whose interval
still contains the base rate. Risk tags from the §3 schema surface here.
Observational — hypothesis ranking, never causal claim.

---

## 8. Probabilistic reasoning

`observe.beta_binomial`: Beta prior centred on base rate (~2 pseudo-observations),
posterior mean + 95% credible interval (scipy exact if available, else normal
approx). Rank by posterior mean *and* interval width — a lucky 3/3 with a wide
interval ranks below 40/50 with a tight one.

---

## 9. Causality guard — ablation is the arbiter

Firing data is confounded (a reflex fires *because* the model erred), so the
probabilistic layer only proposes. Ablation confirms.

```sh
mu dojo measure p8-node-todo --runs 5 --seed 42 --emit-json /tmp/base.json
mu dojo measure p8-node-todo --runs 5 --seed 42 --disable fix_js_duplicate_require \
  --emit-json /tmp/disabled.json
# then: reflexdb.record_efficacy(rid, seed, baseline_hits, n, disabled_hits, n)
```

`sz5_gate(deltas)` encodes the verdict rule: CI excludes 0 across ≥3 seeds.
`record_efficacy()` stores per-seed Δ in `efficacy_run`; updates `reflex.efficacy`
after ≥3 seeds. `mu kb` ablation shortlist orders which to run first.

---

## 10. Relationship to the existing predictor

- `predict.py` (sklearn): `P(success)` from plan-time features — leak-free, prospective.
- Reflex KB: `P(fix | reflexes)` from runtime firings — confounded, exploratory.

They must stay separate: firing data must never enter the plan-time predictor.

---

## 11. Validation discipline

Tests: completeness (`test_registry.py`), ablation hook (`test_reflex_ablation.py`),
combination report (`test_combination_report.py`), idempotency + staleness check
(`test_reflex_idempotency.py`, `idempotent_ids.txt`), efficacy write/read-back +
§5z gate (`test_efficacy.py`), calibration (`test_calibration.py`), ablation rule
(`test_ablation_rule.py`), honesty audit (`honesty_audit()` in `reflexdb.py`).

---

## 12. Risks & honest caveats

- **Confounding:** observational firings can't prove causation — §9 ablation is the sole source of `efficacy`.
- **Small N:** Beta-Binomial shrinkage + interval-aware ranking; never act on a point rate.
- **Determinism:** any learned policy baked offline; runtime runner stays deterministic.
- **Dependency creep:** core is stdlib; `scipy` optional (exact Beta quantiles); `pgmpy` required for the interaction model.
