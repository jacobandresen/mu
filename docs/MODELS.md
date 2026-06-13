# Models — small local models for mu

mu targets **small models on modest hardware** (a Pi, an 8 GB laptop) — that constraint
is the whole point of the reflex layer. Tool-calling reliability is the biggest lever;
the most predictive benchmark for it is **SWE-bench Verified** (real issues, tool use +
multi-file), not HumanEval.

## Recommendation

| Model | VRAM | Role |
|---|---|---|
| `ibm/granite-4.1-3b` | ~2 GB | **Primary** — fits a Pi and 8 GB; 128K context; the dojo's default guest |
| `qwen2.5-coder-7b-instruct` | ~4.5 GB | **Runner-up for 8 GB** — stronger code specialist, tighter context budget |

Bigger machines can run bigger models (e.g. Devstral-Small at 16/32 GB), but mu is tuned
and measured on the two above; everything below assumes the 8 GB envelope.

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
