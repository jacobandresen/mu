# Models — recommendation & characterization

Tool-calling reliability is the single biggest lever. The most predictive benchmark
is **SWE-bench Verified** (real GitHub issues, tool use + multi-file) — not HumanEval.

## Recommendation by VRAM

| Model | VRAM | Notes |
|---|---|---|
| `ibm/granite-4.1-3b` | ~2 GB | **Primary** — fits Pi and 8GB; 128K context |
| `Qwen2.5-Coder-7B-Instruct` | ~4.5 GB | **Runner-up for 8GB** — best code specialist |
| `Devstral-Small-2507` | ~16 GB | 53.6% SWE-bench — recommended for 16GB |
| `Devstral-Small-2` | ~32 GB | **68.0% SWE-bench** — recommended for 32GB |

---

## Integration

mu connects to **LM Studio at `localhost:1234`** via its OpenAI-compatible API
(`src/mu/client.py`); override the host with `MU_LMSTUDIO_HOST`. Starting the
server and loading a model is covered in the [README quick start](../README.md#quick-start).

**Model selection precedence:** `mu agent --model <id>` > `MU_AGENT_MODEL` env
var > the first model loaded in LM Studio.

---

## Tuning (LM Studio, Mac M2 8 GB)

On 8 GB unified memory, CPU + GPU share the pool — headroom is tight (a loaded 7B ≈ 4.5 GB).

- **Context window.** The knob that matters most. `mu dojo run` defaults to `MU_NUM_CTX=8192`, the measured sweet spot for the dojo's `granite-4.1-3b` (~2 GB). Bigger is *not* better: granite scores 3/10 at 8192 but only 1/10 at 16384, where it keeps calling tools but loses coherence in the multi-turn repair loop. A 7B (~4.5 GB) wants less — about 6000; at 8192 it starts swapping (2.6–6× slower) and 16384 isn't viable.

  `client.load_model` loads the model at exactly `MU_NUM_CTX` and verifies the resident context, reloading if LM Studio's 4096-token JIT default capped it lower (otherwise prompts above 4096 are rejected with HTTP 400 mid-run). It does *not* pad above `MU_NUM_CTX`: a 7B loaded at 8048 swap-crashed the host. `MU_LOAD_CTX` overrides the loaded window for machines with RAM to spare.
- **Temperature.** Hardcoded to `0.1` (`client.py`) — low enough for stable structured output, but not a flat `0`, which can send some models into repetition loops.
- **GPU layers.** Leave at the maximum (all on GPU). CPU offload is a 5–10× slowdown.
- **Quantization.** `Q4_K_M` is the sweet spot for 8 GB — it fits with room for the KV cache and still produces correct code. `Q8_0` won't fit alongside a useful context.
- **Memory pressure.** Above ~8096 context on 8 GB, the system runs with almost no free RAM and active swap, which means slower generation and repair-loop timeouts. Timeouts aren't exclusive to large contexts, though — a sustained repair loop can trigger swap even at a low context.

| Parameter | Safe value (M2 8 GB) | Avoid |
|---|---|---|
| Context length | 8192 (granite) / 6000 (7B) | >10000 (OOM/swap) |
| Temperature | 0.1 (mu default) | >0.5 (breaks structured output) |
| GPU layers | All | CPU-only (5–10× slowdown) |
| Quantization | Q4_K_M | Q8_0 (won't fit with context) |

---

## Model characterization (profiles)

The section above is about *picking* a model; this is about *describing* one from its
own data, so that observations, reflexes, skills, and tuning can be attributed to — and
chosen for — a specific model. Granite (3B) and qwen2.5-coder (7B) fail in different
ways, and a profile makes those differences explicit and queryable.

A profile has two layers:

- **Declared** attributes, from the catalog.
- **Empirical** attributes, learned from that model's tagged sessions (`meta.json.model`, via `observe.py`).

Every empirical attribute carries its provenance — the number of sessions and a 95%
credible interval (Beta-Binomial) — so we never characterize a model from three lucky
runs.

Built by `mu kb` (`reflexdb._build_model_profiles`), which writes a `model_profile`
row per model alongside the reflex KB; rebuildable from the session archive, never
hand-edited.

**Capability (empirical, per toolchain)** — `pass_rate`, `first_try_rate`,
`avg_repair_iters`, and `competence_by_toolchain` (`{python:0.9, rust:0.7, …}`, the
practical routing selector — see `mu dojo run --route`).

**Failure fingerprint (the distinctive part)** — a vector over the reflex
`error_class` taxonomy (REFLEX_KB §4): *how often does this model make each class of
mistake?* This is what most distinguishes granite from qwen — e.g. degeneration
(repetition/truncation) is granite-high and near-zero for qwen, so `repeat_penalty`
matters for granite, not qwen. `observe.argue_validity` computes exactly this kind of
per-model claim with intervals: two similar fingerprints **share** lessons; a class
high for one and near-zero for the other is **model-specific**.

**Operational tuning (measured optima)** — `ctx_sweet_spot` (granite 8192; 16384
regresses), `repeat_penalty` (granite 1.1), `stochasticity` (run-to-run variance —
the spread of `mu dojo measure` outcomes with `MU_SEED` set vs unset), and whether
forced `tool_choice` helps (granite yes — kills the prose spiral).

**Honest caveats.**

- The fingerprint says *where* a model errs, not *why* — it is observational.
- A profile is tied to a `model_version`; re-quantizing the model invalidates the empirical fields.
- `competence_by_toolchain` is only comparable when the same problems were run.
- Most cells are sparse, so there is an `n≥5` gate (`observe.Posterior.enough`) and an interval everywhere. Below the gate, an attribute reads "insufficient data" instead of a number.

