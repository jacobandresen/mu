# Model Characterization Scheme

A scheme to characterize each weak model mu drives, so that observations,
reflexes, skills, and tuning can be **attributed to** and **chosen for** a model.
Granite (3B) and qwen2.5-coder (7B) fail in different ways; a model profile makes
those differences explicit, evidence-backed, and queryable.

Two layers: **declared** attributes (known up front, from the catalog) and
**empirical** attributes (learned from that model's tagged sessions —
`meta.json.model`, via `observe.py`). Every empirical attribute carries
provenance: `n` sessions and a 95% credible interval (Beta-Binomial), so we never
characterize a model from three lucky runs.

---

## 1. Identity (declared — from models-catalog.json)

| attribute | example | use |
|---|---|---|
| `id` | `ibm/granite-4.1-3b` | key |
| `family` | granite · qwen2.5 · devstral · mistral | grouping |
| `params_b` | 3 · 7 · 24 | capacity prior |
| `quantization` | Q4_K_M | quality/footprint |
| `context_window` | 128k (declared) | budget ceiling |
| `native_tool_calling` | bool | routing (forced `tool_choice`) |
| `vendor` / `license` | IBM / Apache-2.0 | governance |

## 2. Capability (empirical, per toolchain)

How competent the model is, where. From its tagged sessions, each with a CI:

| attribute | meaning | signal |
|---|---|---|
| `pass_rate` | overall success | meta.outcome |
| `first_try_rate` | passes with zero repair | meta.first_try_pass |
| `avg_repair_iters` | how much repair it needs | meta.repair_iters |
| `competence_by_toolchain` | `{python:0.9, rust:0.7, dotnet:0.3, …}` | outcome × problem.toolchain |
| `max_tier` | hardest complexity reliably passed | problem difficulty × outcome |

`competence_by_toolchain` is the practical selector: route a Rust task to the
model whose Rust CI is highest.

## 3. Failure fingerprint (empirical — the distinctive part)

A vector over the **reflex `error_class` taxonomy** (docs/REFLEX_KB.md §4):
*how often does this model make each class of mistake?* This is the model's
signature — what most distinguishes granite from qwen.

| attribute | meaning | signal |
|---|---|---|
| `error_class_propensity` | `{dependency-hygiene:0.2, degenerate-loop:0.15, missing-import:0.3, …}` | distilled cause / reflex firing × model |
| `degeneration_rate` | repetition-loop / truncation rate | diagnose cause; granite-high |
| `prose_spiral_rate` | emits prose instead of a tool call | retry logs; granite-high, fixed by `tool_choice` |
| `plan_overengineering` | `avg(tasks_total − tasks_needed)` | meta.tasks_total; qwen-high |
| `reflex_reliance` | top reflexes it triggers (which mistakes it makes) | firing logs (reflex KB) |

Two models with similar fingerprints **share** lessons; a class high for one and
near-zero for the other is **model-specific** (e.g. degeneration → granite-only,
so `repeat_penalty` matters for granite, not qwen). `observe.argue_validity`
already computes exactly this kind of per-model claim with intervals.

## 4. Operational tuning (empirical — measured optima)

The knobs, with the value that works for *this* model:

| attribute | meaning | example |
|---|---|---|
| `ctx_sweet_spot` | best `num_ctx` (bigger ≠ better) | granite 8192 (16384 regresses) |
| `repeat_penalty` | anti-degeneration setting | granite 1.1 |
| `temperature` | sampling | 0.1 default |
| `stochasticity` | run-to-run variance | from `mu dojo measure` seeded vs unseeded |
| `tool_choice_required` | forcing helps? | granite yes (kills prose spiral) |

`stochasticity` is itself measurable: the spread of `mu dojo measure` outcomes with
`MU_SEED` unset vs set tells you how reproducible the model is, which sets how
many rounds a fair comparison needs.

## 5. Provenance (on every empirical attribute)

`n_sessions`, `date_range`, `model_version`, and a **credible interval**. Below
`n=5` the attribute reads "insufficient data" rather than a number (the
`observe.Posterior.enough` rule). A profile states what it knows and admits what
it doesn't.

---

## 6. Storage & shape

A **model card** per model: a row in a `model_profile` SQLite table (alongside
the reflex KB) plus a rendered `docs/models/<id>.md`. Declared fields come from
`models-catalog.json`; empirical fields are recomputed by `observe.py` /
`reflexdb.py` from tagged sessions on demand (never hand-edited — rebuildable).

Schema sketch:
```sql
model_profile(
  id TEXT PRIMARY KEY, family TEXT, params_b REAL, context_window INT,
  native_tool_calling INT,
  pass_rate REAL, first_try_rate REAL, avg_repair_iters REAL,
  competence_by_toolchain TEXT,        -- json
  error_class_propensity TEXT,         -- json (the fingerprint)
  degeneration_rate REAL, plan_overengineering REAL,
  ctx_sweet_spot INT, repeat_penalty REAL, stochasticity REAL,
  n_sessions INT, ci_json TEXT, updated TEXT
);
```

---

## 7. What the scheme buys us

1. **Transfer reasoning:** compare two fingerprints → decide if an observation /
   reflex / skill learned on model A applies to model B (shared class) or is
   A-specific (diverging class). Concrete answer to "is this observation valid
   for each model."
2. **Per-model configuration:** load granite-specific skills/tuning
   (`repeat_penalty`, forced `tool_choice`, ctx=8192) from granite's profile;
   don't pay that cost for qwen.
3. **Model selection / routing:** pick the model whose `competence_by_toolchain`
   best matches the task.
4. **Honest comparison:** the dojo's README pass table becomes per-model with
   intervals, so "granite 3/10, qwen 8/10" is stated with the uncertainty it
   deserves.

## 8. How profiles are built & validated

- **Build:** `mu model-profile [--model X]` aggregates tagged sessions via
  `observe.py` → writes the `model_profile` row + the rendered card. Pure
  read-over-archive; rebuildable.
- **Data:** run the dojo per model — `mu dojo practice --model ibm/granite-4.1-3b`
  and `mu dojo practice --model qwen/qwen2.5-coder-7b-instruct` — each ≥5 rounds
  so the cells clear the `n≥5` bar.
- **Validate (descriptive):** credible-interval calibration test (as in
  REFLEX_KB §12.3) — simulate known per-model rates, assert 95% coverage.
- **Validate (causal):** any *configuration* a profile recommends
  (e.g. "granite needs `repeat_penalty`") is confirmed by **ablation**:
  `mu dojo measure` with the knob on vs off, on that model's frozen seeded baseline,
  Δ with a credible interval excluding 0. The profile proposes; ablation proves.

---

## 9. Honest caveats

- **Observational:** the fingerprint says *where a model errs*, not *why*; it is
  built from sessions where the model already failed/passed, so it describes
  tendencies, not mechanisms.
- **Version drift:** a profile is tied to a `model_version`; re-quantizing or
  updating the model invalidates the empirical fields (declared fields persist).
- **Confounding with problem mix:** `competence_by_toolchain` is only fair when
  the same problems were run; record the problem set in provenance.
- **Small N is the norm:** most cells will be sparse — hence the `n≥5` gate and
  intervals everywhere. Characterize cautiously.
