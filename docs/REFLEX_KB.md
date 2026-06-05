# Reflex Knowledge Base — Design & Reference

Status: **implemented** (`reflexes/registry.py`, `reflexdb.py`, `observe.py`; built
by `mu kb`). Turns ~80 ad-hoc reflexes into a queryable, de-duplicated knowledge
base and reasons **probabilistically** about which reflexes (and combinations) help —
without overclaiming from confounded data.

---

## 1. Motivation

Reflexes (`src/mu/reflexes/`) are deterministic condition→action fixers, discovered
one at a time from dojo failures, grouped physically by language, and chained to a
fixpoint by `run_reflexes`. The KB adds machine-readable metadata so we can answer:

- **Inventory:** what exists, what overlaps, what generalises across toolchains?
- **Efficacy:** which reflexes move the pass rate, and which fire but never matter?
- **Combination:** which reflexes work as a bundle; which contradict; in what order?

The KB is **observational and exploratory by construction**; the causal arbiter remains
`mu dojo measure` ablation (§9). The KB *ranks hypotheses*; ablation *confirms* them.

Non-goals: feeding reflex-firing data into the plan-time `predict.py` (would leak the
label — §10); online/random reflex selection (would break `MU_SEED` reproducibility).

---

## 2. Architecture

```
session archive (~/.mu/sessions/*)         # source of truth
        │  mine logs
        ▼
~/.mu/mu.db  (SQLite, rebuildable via `mu kb`)
   ├── reflex   (static catalog, from reflexes.registry)
   ├── session  (outcome labels, tagged with model)
   ├── firing   (one row per reflex application)
   └── model_profile (per-model aggregates — docs/MODELS.md)
        │
        ├── SQL co-occurrence / conditional report (§7)
        ├── Beta-Binomial posteriors (observe.py, §8)
        └── ablation (MU_DISABLE_REFLEX + mu dojo measure) → causal efficacy (§9)
```

Dependency posture: `sqlite3` + `math` are stdlib. The probabilistic core is a small
named function; `scipy.stats`/`pgmpy` are **optional** upgrades, gated like
`scikit-learn` in `predict.py`. Layers depend one way — mining (facts) → SQL
aggregation (counts) → probability (beliefs) → ablation (truth); none reaches back up.

---

## 3. Characterising a reflex — the schema

One row per reflex; every field derivable from code or cheap to curate. The `reflex`
table and the registry record *are* the per-reflex docs — a reader learns a reflex
from its row, not its body.

| Attribute | Type / vocabulary | Source |
|---|---|---|
| `id` | text PK — function name | code |
| `summary` | text — one line | docstring |
| `toolchain` | python·rust·go·csharp·js·makefile·cargo·npm·dotnet·`*` | module |
| `artifact` | source·manifest·makefile·plan·test-config | code |
| `error_class` | controlled vocab (§4) | curated |
| `trigger` | scan·lint-out·test-out·project·plan | function signature |
| `phase` | write·lint-repair·test-repair·pre-flight·plan | call site |
| `idempotent` | bool (`f(f(x))==f(x)` — the fixpoint runner depends on it) | test |
| `scope` | file·project·multi-file | signature |
| `risk` | syntactic-safe·heuristic·intent-reconstruction | curated |
| `evidence` | dojo problem + cause + commit that surfaced it | git/CHALLENGES |
| `efficacy` | Δ pass-rate from ablation (null until measured) | §9 |

`reflexes/registry.py` builds these records from the reflex function objects (id from
`__name__`, toolchain from `__module__`, trigger from `inspect.signature`); `reflexdb.py`
upserts them into the `reflex` table.

---

## 4. Grouping — two orthogonal axes

- **Physical:** by toolchain (the modules). Code locality.
- **Semantic:** by `error_class` — the cross-language lens:

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

Several semantic groups are *one algorithm + a per-toolchain table*; the target is a
**generic core + thin adapter** (a new toolchain = add `(parser, predicate)`):

- dependency-hygiene → `strip_manifest_deps(manifest, parse, forbidden_pred)` — Cargo
  (invalid semver), requirements.txt (stdlib), package.json (node builtins).
- duplicate-declaration → `dedupe_top_level_decls(text, decl_regex)`.
- missing-symbol-import → `resolve_undefined(names, sibling_sources, fmt_import)`.

The `error_class` field makes each family visible, so the refactor target is obvious;
refactors are behaviour-preserving and gated by golden tests.

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
  session_id TEXT, reflex_id TEXT, file TEXT, pass_index INT, phase TEXT, ts TEXT,
  FOREIGN KEY(session_id) REFERENCES session(session_id),
  FOREIGN KEY(reflex_id)  REFERENCES reflex(id)
);
```

`firing` is the heart: `pass_index` gives sequence, the session join gives the outcome,
self-joins give co-occurrence. The DB is **rebuildable** from the archive (`mu kb`), so
it is never the source of truth.

---

## 7. Combination analysis — pure SQL

```sql
-- conditional success: P(success | reflex)
SELECT f.reflex_id, AVG(s.success) p_success, COUNT(*) n
FROM firing f JOIN session s USING(session_id) GROUP BY 1 ORDER BY n DESC;
-- sequence: "A enables B" (A fires on an earlier pass than B)
SELECT a.reflex_id before_, b.reflex_id after_, COUNT(*) n
FROM firing a JOIN firing b ON a.session_id=b.session_id AND a.pass_index<b.pass_index
GROUP BY 1,2 ORDER BY n DESC;
```

Lift = `P(A,B)/(P(A)·P(B))`. Synergy = `P(✓|A,B) > max(P(✓|A),P(✓|B))`; the reverse is
an antagonism (contradiction) signal.

---

## 8. Probabilistic reasoning

Raw rates lie at small N — model the uncertainty (`observe.beta_binomial`). Each
reflex/combo outcome is Bernoulli with a `Beta(α₀,β₀)` prior centred on the base rate
`r̄` (a weak prior ~2 pseudo-observations). After `s` successes / `f` failures:

```
α = α₀ + s,  β = β₀ + f
P̂(✓) = α/(α+β)                          # posterior mean, shrinks small-N → r̄
95% credible interval = Beta(α,β).ppf([.025,.975])   # scipy optional; else normal approx
```

Rank by **posterior mean *and* interval width**: a combo at 3/3 with a wide interval
ranks below 40/50 with a tight one — the honest fix for the "lucky 5/5" trap. The
decision question — *which reflex set maximises P(fixed) for error signature E?* — is
used to **offline-learn a fixed chain order** baked into the runner, never online
sampling (which would reintroduce non-determinism). A small Bayesian net
`features → error_class → {reflexes} → outcome` (hand-rolled CPTs; `pgmpy` optional)
can capture interactions and learned contradictions, complementing the runner's cycle
guard.

---

## 9. Causality guard — ablation is the arbiter

Firing data is **observational and confounded**: a reflex fires *because* the model
erred, so `P(✓|A)` is entangled with problem difficulty. The probabilistic layer
**proposes**; it never concludes. Causal test: `MU_DISABLE_REFLEX=<id>` (read by
`run_reflexes`) on a **frozen, seeded** baseline (`mu dojo measure` + `MU_SEED`),
re-measure, read Δ pass-rate and Δ repair-iters. That Δ — not the posterior — is what
`reflex.efficacy` records. Posteriors merely order which ablations to run first.

---

## 10. Relationship to the existing predictor

- `predict.py` (sklearn): `P(success)` from **plan-time** features — leak-free,
  prospective, feeds the planner.
- Reflex KB (this): `P(fix | reflexes)` from **runtime** firings — confounded,
  exploratory, used to bundle reflexes and prioritise ablations.

Different stages; they must stay separate. Reflex firings must never enter the
plan-time predictor (the firing happened *because* of the eventual outcome).

---

## 11. Validation discipline

How we know a KB-driven change is real, not noise:

- **Completeness (CI):** every public `fix_*` in `reflexes/` is registered with
  non-null required fields, and `error_class`/`trigger`/`phase`/`risk` ∈ controlled
  sets. `registry.unregistered()` enforces it.
- **Idempotency:** each `scan` reflex satisfies `f(f(x)) == f(x)` on a recorded fixture
  — the property the fixpoint runner depends on.
- **Interval calibration:** simulate K reflexes with known true rates, build 95%
  intervals, assert empirical coverage ∈ [0.93, 0.97]. A miscalibrated estimator fails.
- **Ablation = causal proof:** any "this reflex/combo helps (or is dead weight)" claim
  promoted to a code change must clear an ablation Δ whose **credible interval excludes
  0** across ≥3 seeds — never a single lucky round (AGENTS §5z). The
  `fix_js_duplicate_require` positive control (disable on the frozen p8 baseline → the
  duplicate-`fs` SyntaxError returns; enable → gone) is pinned as a regression fixture.
- **No regression:** after any KB-driven change, the frozen-baseline suite
  (`mu dojo measure` over all problems × ≥3 seeds) shows pass-rate non-decreasing.
- **Honesty audit:** the KB surfaces any reflex whose `evidence` ties it to exactly one
  dojo problem with a problem-specific pattern, for human review (AGENTS §0/§2).

---

## 12. Risks & honest caveats

- **Confounding:** observational firing data cannot prove causation — §9 ablation is the
  sole source of `efficacy`; the probabilistic layer is explicitly hypothesis generation.
- **Small N:** many reflexes fire rarely — Beta-Binomial shrinkage + interval-aware
  ranking; never act on a point rate.
- **Determinism:** all learned policy (chain order) is baked **offline**; the runtime
  runner stays deterministic so `MU_SEED` reproducibility holds.
- **Dependency creep:** core is stdlib (`sqlite3`, `math`); `scipy`/`pgmpy` optional.
