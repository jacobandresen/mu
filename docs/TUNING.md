# LM Studio Tuning Guide — Mac M2 8 GB

Observations collected from dojo sessions running qwen3:8b and gemma4:e2b on a MacBook with M2 (8 GB unified memory). mu uses LM Studio as its backend via the OpenAI-compatible API at `localhost:1234`.

---

## Hardware context

| Property | Value |
|----------|-------|
| SoC | Apple M2 (unified memory) |
| Total RAM | 8 GB |
| Memory architecture | CPU + GPU share the same pool |
| Page size | 16 KB (not 4 KB as on x86) |

With only 8 GB shared between OS, GPU, and the model, headroom is tight.
A fully loaded qwen3:8b occupies roughly 6 GB, leaving ~2 GB for the system.

---

## Key parameters

### 1. Context window

Set in LM Studio when loading the model (Model Settings → Context Length), or passed as `max_tokens` in the API request.

| Value | KV cache | Behaviour |
|-------|----------|-----------|
| 2048 | ~150 MB | Very fast; too small for multi-file tasks |
| 4096 | ~300 MB | Default; works for simple tasks, risks truncation on complex ones |
| 6000 | ~450 MB | Good balance — fits most code tasks without swap pressure |
| 8096 | ~600 MB | More context, triggers swap on 8 GB M2, noticeably slower |
| 16384 | ~1.2 GB | Not viable on 8 GB M2 — excessive swap |

**Recommendation:** 6000 on M2 8 GB. It gives enough room for multi-file code tasks without pushing the system into heavy swap. Use 8096 only if a problem consistently fails at 6000 (e.g. very long prompts).

**Measured impact:** Doubling ctx from 4096 → 8096 made P1 2.6× slower (64 s → 165 s) and P3 6× slower (155 s → 928 s). The extra swap I/O dominates for long sessions.

---

### 2. Temperature

mu passes `temperature: 0.1` in every API request (hardcoded in `src/mu/client.py`). This is intentional:

| Value | Effect |
|-------|--------|
| 0 | Fully deterministic — always picks the highest-probability token |
| 0.1 | Very low randomness; stable structured output; mu default |
| 0.7 | Default for many UIs; too creative for code generation |
| 1.0+ | High variance; poor for structured outputs like PLAN.md |

0.1 (rather than 0) avoids repetition loops that pure greedy decoding can produce on some models.

---

### 3. GPU layers

LM Studio offloads model layers to the M2 GPU automatically. Leave this at maximum (all layers on GPU). Moving layers to CPU dramatically reduces throughput — the KV cache and CPU overhead are already the binding constraint on 8 GB.

---

### 4. Concurrent requests

LM Studio defaults to processing one request at a time. mu's agent loop is sequential (plan → write → lint → test), so there is never concurrent inference within one dojo problem. No change needed.

---

### 5. Quantization — Model weight precision

| Format | Size | Decode speed | Quality |
|--------|------|-------------|---------|
| Q2_K | ~3.0 GB | Fastest | Noticeably degraded |
| Q4_K_M | ~5.2 GB | Good (15–25 tok/s on M2) | Slightly below fp16 |
| Q6_K | ~6.5 GB | Slower | Near-lossless |
| Q8_0 | ~8.7 GB | Slow | Very close to fp16 |
| fp16 | ~16 GB | Slowest | Exact |

Q4_K_M is the sweet spot for 8 GB M2:
- Fits with room for system + 6000-context KV cache
- Produces correct, idiomatic code for all tested problems (P1–P7)
- Q8_0 does not fit in 8 GB alongside a 6000+ context

**Recommendation:** Keep Q4_K_M. Don't try Q8_0 on 8 GB — you'll swap constantly.

---

## Model recommendation for M2 8 GB

| Model | Size | Notes |
|-------|------|-------|
| **qwen2.5-coder:7b Q4_K_M** | ~4.5 GB | Best 8 GB option; 88.4% HumanEval; native tool calling |
| **gemma4:e2b** | 7.2 GB | Very fast writes; repair tool-call unreliable on hard tasks |
| qwen3:8b Q4_K_M | 5.2 GB | General model; strong planning; 6/7 in v0.3 with repair loop |

Use qwen2.5-coder:7b for the best balance of speed and code quality on 8 GB.

---

## Recommended LM Studio setup

1. Load model in LM Studio → set Context Length to 6000
2. Start the local server (Developer → Start Server)
3. Run mu:

```sh
mu agent "your goal"
# or pin a specific model:
export MU_AGENT_MODEL=qwen/qwen2.5-coder-7b-instruct
mu agent "your goal"
```

---

## Memory pressure warning

At 8096 context on 8 GB M2, the system runs with only ~44 MB free physical RAM and 1.5 GB swap active. This manifests as:
- Slower generation (swap I/O latency)
- Occasional kernel page-compression stalls
- Repair sessions hitting timeout

**Timeouts are not exclusive to large contexts.** Even at 3072 context, a sustained repair loop (~2000 combined prompt + completion tokens) is enough to trigger swap pressure on 8 GB. Lower context reduces *baseline* memory use but does not eliminate timeout risk under sustained generation load.

---

## Summary table

| Parameter | Safe value for M2 8 GB | Avoid |
|-----------|----------------------|-------|
| Context length | 6000 | >10000 (OOM) |
| Temperature | 0.1 (mu default) | >0.5 (breaks structured output) |
| GPU layers | All (LM Studio default) | CPU-only (5–10× slowdown) |
| Quantization | Q4_K_M | Q8_0 (doesn't fit in 8 GB with context) |
