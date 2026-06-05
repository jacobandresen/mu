# Models — recommendation & characterization

## What the dojo requires

Seven problems across Python, C (SDL2), C# (dotnet), Go (Gin), Rust (cargo), and a hard Flask+SQLite+pytest problem.
The top failure modes (from DOJO.md) are:

1. **Tool calling failure** — model generates prose instead of calling Write; repair agent never acts.
2. **API hallucination** — wrong library versions (gin v2.0.0), SDL3 vs SDL2 APIs, bad go.mod pins.
3. **Makefile syntax** — spaces instead of tabs, orphan commands, wrong SDL2 wiring.
4. **Multi-language breadth** — model must write idiomatic Python, C, Go, Rust, C# in one session.

Tool calling reliability is the single biggest lever: gemma4:e2b hit 5/7 with sensors but collapsed
on P2/P7 every time because the repair agent generated explanations instead of tool calls.

The most predictive benchmark for the dojo is **SWE-bench Verified** (fixing real GitHub issues with
tools) — not HumanEval (Python autocomplete). Models that score well on SWE-bench have demonstrated
they can call tools, iterate on failures, and write correct multi-file code.

---

## Recommendation by VRAM

| Model | Dojo problem | Notes |
|---|---|---|
| `google/gemma-4-e2b` | Repair agent never calls tools (CHALLENGES #1, #9) | Fast but unreliable; fails P2/P7 every run |
| `mistralai/mistral-7b-instruct-v0.3` | General model, pre-2025, no code specialization | Likely worse than Qwen2.5-Coder on multi-lang code |
| `ibm/granite-4.1-3b` | ~2 GB; fits Pi and 8GB machines; 128K context | **Primary recommendation** |
| `Qwen2.5-Coder-7B-Instruct` | Best 8GB code specialist | **Runner-up for 8GB** |
| `Devstral-Small-2507` | Agentic, 53.6% SWE-bench | **Recommended for 16GB** |
| `Devstral-Small-2` | Agentic, **68.0% SWE-bench** | **Recommended for 32GB** |

SWE-bench Verified (real GitHub issues, tool use + multi-file debugging) is the most
predictive benchmark for the dojo — not HumanEval. Tool-calling reliability is the single
biggest lever.

---

## Integration

mu connects to **LM Studio at `localhost:1234`** via its OpenAI-compatible API (`src/mu/client.py`).
Override the host with `MU_LMSTUDIO_HOST`.

To use a model with mu:

1. Load it in LM Studio (Models tab → load)
2. Start the local server (LM Studio → Developer → Start Server)
3. Run:
   ```
   mu agent --model <model-id> "your goal"
   ```
   Or set the env var permanently:
   ```
   export MU_AGENT_MODEL=qwen/qwen2.5-coder-7b-instruct
   ```

If `--model` and `MU_AGENT_MODEL` are both unset, mu uses the first model loaded in LM Studio.

---

## Tuning (LM Studio, Mac M2 8 GB)

On 8 GB unified memory, CPU + GPU share the pool — headroom is tight (a loaded 7B ≈ 4.5 GB).

- **Context window.** `mu dojo run` defaults to `MU_NUM_CTX=8192`, the measured sweet spot for the dojo's `granite-4.1-3b` (~2 GB): bigger is *not* better — 8192 → 3/10 vs 16384 → 1/10 (at 16384 it keeps tool-calling but loses coherence in the multi-turn repair loop). For a 7B (~4.5 GB), ~6000 is the balance — 8192 triggers swap (measured 2.6–6× slower), 16384 isn't viable. `client.load_model` loads with `MU_NUM_CTX + 2048` headroom; without it LM Studio's 4096 JIT default silently caps the model and prompts >4096 are rejected HTTP 400 mid-run. Override with `MU_NUM_CTX` / `MU_LOAD_CTX`.
- **Temperature.** mu hardcodes `0.1` (`client.py`) — low randomness for stable structured output; 0.1 rather than 0 avoids the repetition loops pure greedy decoding triggers on some models.
- **GPU layers.** Leave at max (all on GPU); CPU offload is a 5–10× slowdown.
- **Quantization.** `Q4_K_M` is the sweet spot for 8 GB — fits with room for the KV cache and produces correct code; `Q8_0` doesn't fit alongside context.
- **Memory pressure.** Above ~8096 ctx on 8 GB the system runs near-zero free RAM with active swap → slower generation and repair-loop timeouts. Timeouts aren't exclusive to large contexts: a sustained repair loop can trigger swap even at low ctx.

| Parameter | Safe value (M2 8 GB) | Avoid |
|---|---|---|
| Context length | 8192 (granite) / 6000 (7B) | >10000 (OOM/swap) |
| Temperature | 0.1 (mu default) | >0.5 (breaks structured output) |
| GPU layers | All | CPU-only (5–10× slowdown) |
| Quantization | Q4_K_M | Q8_0 (won't fit with context) |

---

## Model characterization (profiles)

The section above is about *picking* a model; this is about *describing* one from
data, so observations, reflexes, skills, and tuning can be attributed to and chosen
for a model. Granite (3B) and qwen2.5-coder (7B) fail in different ways; a profile
makes those differences explicit and queryable. Two layers: **declared** attributes
(from the catalog) and **empirical** attributes (learned from that model's tagged
sessions — `meta.json.model`, via `observe.py`). Every empirical attribute carries
provenance — `n` sessions and a 95% credible interval (Beta-Binomial) — so we never
characterize a model from three lucky runs.

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

**Honest caveats.** The fingerprint says *where* a model errs, not *why* (it's
observational). A profile is tied to a `model_version` — re-quantizing invalidates the
empirical fields. `competence_by_toolchain` is only fair when the same problems were
run. Most cells are sparse — hence the `n≥5` gate (`observe.Posterior.enough`) and
intervals everywhere; below it the attribute reads "insufficient data" rather than a
number.

