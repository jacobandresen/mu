# Models — small local models for mu

mu targets **small models on modest hardware** (a Pi, an 8 GB laptop) — that constraint
is the whole point of the reflex layer. Tool-calling reliability is the biggest lever;
the most predictive benchmark for it is **SWE-bench Verified** (real issues, tool use +
multi-file), not HumanEval.

## Recommendation

| Model | Resident | Role |
|---|---|---|
| `qwen2.5-coder-7b-instruct` **Q3_K_L** | 4.09 GB | **Primary on 8 GB** — measured **7.0/10** on the L0 board, the best that runs here (see trials below). Pin the served id `qwen2.5-coder-7b-instruct` |
| `ibm/granite-4.1-3b` | ~2 GB | **Lightweight fallback** — fits a Pi; 128K context; but only ~2.75/10 here, too weak past simple problems |

The 7B **Q4_K_M** (~4.7 GB) does **not** fit (it exhausts RAM); **Q3_K_L** (3.8 GB on
disk) is the quant that runs. Models >~4.1 GB resident hit a GPU `Compute error` on 8 GB
(see trials). Bigger machines can run bigger models (e.g. Devstral-Small at 16/32 GB),
but mu is tuned and measured on the above; everything below assumes the 8 GB envelope.

## Integration

mu connects to **LM Studio at `localhost:1234`** via its OpenAI-compatible API
(`src/mu/client.py`); override the host with `MU_LMSTUDIO_HOST`. Starting the server and
loading a model is in the [README quick start](../README.md#quick-start).

**Model selection precedence:** `mu agent --model <id>` > `MU_AGENT_MODEL` > the first model
loaded in LM Studio.

## Tuning (M2 8 GB)

On 8 GB unified memory CPU + GPU share the pool, so headroom is tight (a loaded 7B ≈ 4.5 GB).
The knob that matters most is the **context window** (`MU_NUM_CTX`):

| Model | Sweet spot | Why |
|---|---|---|
| granite-3b (~2 GB) | **8192** | 3/10 at 8192 but only 1/10 at 16384 — it keeps calling tools but loses coherence in the repair loop |
| qwen-7b (~4.5 GB) | **6000** | at 8192 it swaps (2.6–6× slower); 16384 isn't viable |

`client.load_model` loads at exactly `MU_NUM_CTX` and reloads if LM Studio's 4096-token JIT
default capped it lower; it never pads above `MU_NUM_CTX` (a 7B loaded at 8048 swap-crashed
the host). `MU_LOAD_CTX` overrides for machines with RAM to spare.

Other settings: **temperature** is `0.1` (low enough for stable structured output, not a flat
`0` that loops); keep **all GPU layers** (CPU offload is 5–10× slower); **Q4_K_M** quantization
is the 8 GB sweet spot (`Q8_0` won't fit alongside a useful context). Above ~8 K context on
8 GB the host runs near-zero free RAM with active swap → slow generation and repair-loop
timeouts.

## Model trials on the M2 8 GB host (2026-06-20)

Empirical load/fit/capability log for *this specific 8 GB M2*, to settle which model
the dojo (p10 plan) should run on. LM Studio guardrails are **off**
(`modelLoadingGuardrails.mode=off`, `customThresholdBytes≈7 GB`), so a refusal to load
is genuine RAM exhaustion, not a policy block. All loads via
`lms load <id> -c 6000 --gpu max`.

| Model (quant) | Disk | Resident | Loads on 8 GB? | p1 smoke | Notes |
|---|---|---|---|---|---|
| qwen2.5-coder-**7b** Q4_K_M (~4.7 GB) | — | — | **No** — "insufficient resources" | — | the *documented blocker*; not currently on disk |
| qwen2.5-coder-**7b** **Q3_K_L** | 3.8 GB | **3.81 GiB** | **Yes** (~15 s load) | **PASS, 47 s** | ~1 GB swap, stable; **the fit-capable 7b** |
| qwen2.5-coder-**7b** Q2_K | 2.8 GB | ~2.9 GiB (est.) | Yes (untested capability) | — | smaller fallback; Q2 quality degraded — only if Q3_K_L proves too heavy |
| qwen2.5-coder-**3b** Q4_K_M (current pin) | 2.1 GB | ~2.1 GiB | Yes | PASS | **too weak past hello-world** — L0 board (N=5) solved only p1 |
| ibm/granite-4.1-3b | 2.1 GB | ~2.1 GiB | Yes | PASS | prior primary; same 3b-class ceiling |

**Findings.**
- The "7B won't load on 8 GB" note (in `.zshrc`, README, and line 35 above) was the
  **Q4_K_M** (~4.7 GB). The **Q3_K_L** quant (3.8 GB) *does* fit — 3.81 GiB resident,
  loads in ~15 s, p1 end-to-end in 47 s, ~1 GB swap and stable. So the choice is **not**
  "3b vs nothing" — a real 7b *is* runnable here, one quant step down from Q4.
- **Model-id gotcha:** `client.chat` passes `MU_AGENT_MODEL` **verbatim** to
  `/v1/models`, so the pin must equal the id LM Studio serves. LM Studio uses the **bare**
  name (`qwen2.5-coder-7b-instruct`) when it's unique, but **org-prefixes on collision**:
  while a second 7b (the `qwen/…` Q2_K) was also present, both showed as
  `lmstudio-community/…` and `qwen/…`. With only the Q3_K_L kept, the served id is the bare
  `qwen2.5-coder-7b-instruct` — that's the pin. Always check `curl localhost:1234/v1/models`.
- **Capability comparison — L0 board, N=5 over all ten problems** (`E[#solved]` =
  observed problems solved /10):

  | Model | Quant | Resident | observed /10 | Runs on 8 GB? |
  |---|---|---|---|---|
  | **qwen2.5-coder-7b** | **Q3_K_L** | 4.09 GB | **7.0** ✅ winner | yes |
  | seed-coder-8b | Q3_K_S | 3.80 GB | 5.6 | yes |
  | granite-4.1-3b | Q4 | 2.10 GB | ~2.75 (partial) | yes but crawls @8192 |
  | qwen2.5-coder-3b | Q4 | 2.10 GB | 0.8 | yes |
  | qwen3-8b | Q4 | 4.43 GB | — | **no — Compute error** |
  | granite-3.3-8b | Q3_K_L | 4.35 GB | — | **no — Compute error** |

- **The 8 GB GPU ceiling (key finding).** Models **>~4.1 GB resident fail every
  inference** with LM Studio `400 {"error":"Compute error."}` at full Metal offload
  (`--gpu max`): the weights + KV + compute graph exceed the GPU budget, so the model
  *loads* but cannot *run*. qwen3-8b (4.43 GB) and granite-3.3-8b (4.35 GB) both hit
  this; lowering ctx 6000→4096 did **not** help (it's the weight buffers, not KV).
  They *do* run at **partial offload** (`--gpu 0.5`, layers on CPU) but that's 5–10×
  slower — impractical for the dojo. So **~4.1 GB resident is the hard runnable
  ceiling here**, and qwen2.5-coder-7b Q3_K_L is the largest/strongest model under it.
- seed-coder-8b (the SWE-bench-Verified leader at 8B) *runs* but lands at 5.6/10 —
  notably it scores **0/5 on p3-sdl2 and p7-flask** (weaker on those toolchains),
  confirming the headline benchmark doesn't map directly to this multi-language,
  tool-use, multi-file dojo. **Recommendation: pin `qwen2.5-coder-7b-instruct`
  (Q3_K_L) — served id `qwen2.5-coder-7b-instruct`.**

## Per-model profiles

granite (3B) and qwen (7B) fail differently, so `mu kb` builds a `model_profile` per model
from its tagged sessions (`meta.json.model`, via `observe.py`) — rebuildable from the archive,
never hand-edited. Each profile carries **capability** (`pass_rate`, `first_try_rate`,
`competence_by_toolchain` — the `mu dojo run --route` selector), a **failure fingerprint**
over the reflex `error_class` taxonomy (degeneration is granite-high, near-zero for qwen — so
`repeat_penalty` matters for granite, not qwen), and **measured tuning optima** (`ctx_sweet_spot`,
`repeat_penalty`, whether forced `tool_choice` helps — yes for granite). Every empirical field
has an `n≥5` gate and a Beta-Binomial interval, so a model is never characterised from three
lucky runs. See [REFLEX_KB.md](REFLEX_KB.md) for the `error_class` taxonomy.
